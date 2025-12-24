'use strict';

import { la } from './utils.js';
import { Storage } from './storage.js';

// Alphabetical order
// Браузерные коды - основные для отображения в UI
// Electron-коды добавлены как псевдонимы (aliases)
const available_langs = {
  "ar_ar": { "name": "العربية", "file": "ar_ar.json", "direction": "rtl", "aliases": ["ar"] },
  "bg_bg": { "name": "Български", "file": "bg_bg.json", "direction": "ltr", "aliases": ["bg"] },
  "cz_cz": { "name": "Čeština", "file": "cz_cz.json", "direction": "ltr", "aliases": ["cs"] },
  "da_dk": { "name": "Dansk", "file": "da_dk.json", "direction": "ltr", "aliases": ["da"] },
  "de_de": { "name": "Deutsch", "file": "de_de.json", "direction": "ltr", "aliases": ["de"] },
  "es_es": { "name": "Español", "file": "es_es.json", "direction": "ltr", "aliases": ["es"] },
  "fa_fa": { "name": "فارسی", "file": "fa_fa.json", "direction": "rtl", "aliases": ["fa"] },
  "fr_fr": { "name": "Français", "file": "fr_fr.json", "direction": "ltr", "aliases": ["fr"] },
  "hu_hu": { "name": "Magyar", "file": "hu_hu.json", "direction": "ltr", "aliases": ["hu"] },
  "it_it": { "name": "Italiano", "file": "it_it.json", "direction": "ltr", "aliases": ["it"] },
  "jp_jp": { "name": "日本語", "file": "jp_jp.json", "direction": "ltr", "aliases": ["ja"] },
  "ko_kr": { "name": "한국어", "file": "ko_kr.json", "direction": "ltr", "aliases": ["ko"] },
  "nl_nl": { "name": "Nederlands", "file": "nl_nl.json", "direction": "ltr", "aliases": ["nl"] },
  "pl_pl": { "name": "Polski", "file": "pl_pl.json", "direction": "ltr", "aliases": ["pl"] },
  "pt_br": { "name": "Português do Brasil", "file": "pt_br.json", "direction": "ltr", "aliases": [] },
  "pt_pt": { "name": "Português", "file": "pt_pt.json", "direction": "ltr", "aliases": [] },
  "rs_rs": { "name": "Srpski", "file": "rs_rs.json", "direction": "ltr", "aliases": ["sr"] },
  "ru_ru": { "name": "Русский", "file": "ru_ru.json", "direction": "ltr", "aliases": ["ru"] },
  "tr_tr": { "name": "Türkçe", "file": "tr_tr.json", "direction": "ltr", "aliases": ["tr"] },
  "ua_ua": { "name": "Українська", "file": "ua_ua.json", "direction": "ltr", "aliases": ["uk"] },
  "vi_vn": { "name": "Tiếng Việt", "file": "vi_vn.json", "direction": "ltr", "aliases": ["vi"] },
  "zh_cn": { "name": "中文", "file": "zh_cn.json", "direction": "ltr", "aliases": [] },
  "zh_tw": { "name": "中文(繁)", "file": "zh_tw.json", "direction": "ltr", "aliases": [] }
};

// Карта для быстрого поиска языка по любому коду (основному или алиасу)
const lang_code_map = {};
Object.keys(available_langs).forEach(browserCode => {
  const lang = available_langs[browserCode];
  // Добавляем основной код
  lang_code_map[browserCode] = browserCode;
  // Добавляем все алиасы
  lang.aliases.forEach(alias => {
    lang_code_map[alias] = browserCode;
  });
});

// Translation state - will be imported from core.js app object
let translationState = null;
let welcomeModal = null;
let handleLanguageChange = null;

export function lang_init(appState, handleLanguageChangeCb, welcomeModalCb) {
  translationState = appState;
  handleLanguageChange = handleLanguageChangeCb;
  welcomeModal = welcomeModalCb;
  
  let id_iter = 0;
  const items = document.getElementsByClassName('ds-i18n');
  for(let item of items) {
    if (item.id.length == 0) {
      item.id = `ds-i18n-${id_iter++}`;
    }
    
    translationState.lang_orig_text[item.id] = $(item).html();
  }
  translationState.lang_orig_text[".title"] = document.title;
  
  const force_lang = Storage.getString("force_lang");
  if (force_lang != null) {
    lang_set(force_lang, true).catch(error => {
      console.error("Failed to set forced language:", error);
    });
  } else {
    const nlang = navigator.language.replace('-', '_').toLowerCase();
    // Ищем язык по коду (браузерному или electron)
    const browserLang = lang_code_map[nlang];
    if (browserLang) {
      const langData = available_langs[browserLang];
      la("lang_init", {"l": nlang});
      lang_translate(langData["file"], browserLang, langData["direction"]).catch(error => {
        console.error("Failed to load initial language:", error);
      });
    }
  }
  
  // Строим список только из браузерных кодов (без дубликатов)
  const olangs = [
    '<li><a class="dropdown-item" href="#" onclick="lang_set(\'en_us\');">English</a></li>',
    ...Object.keys(available_langs).map(browserCode => {
      const name = available_langs[browserCode]["name"];
      return `<li><a class="dropdown-item" href="#" onclick="lang_set('${browserCode}');">${name}</a></li>`;
    }),
    '<li><hr class="dropdown-divider"></li>',
    '<li><a class="dropdown-item" href="https://github.com/dualshock-tools/dualshock-tools.github.io/blob/main/TRANSLATIONS.md" target="_blank">Missing your language?</a></li>'
  ].join('');
  $("#availLangs").html(olangs);
}

async function lang_set(lang, skip_modal=false) {
  la("lang_set", { l: lang });
  
  // Преобразуем переданный код в браузерный код (если это electron-код)
  const browserLang = lang_code_map[lang] || lang;
  
  lang_reset_page();
  if(browserLang != "en_us") {
    const langData = available_langs[browserLang];
    if (langData) {
      await lang_translate(langData["file"], browserLang, langData["direction"]);
    } else {
      console.error(`Language not found: ${lang} (browser: ${browserLang})`);
    }
  }
  
  await handleLanguageChange(browserLang);
  Storage.setString("force_lang", browserLang);
  if(!skip_modal && welcomeModal) {
    Storage.setString("welcome_accepted", "0");
    welcomeModal();
  }
}

function lang_reset_page() {
  lang_set_direction("ltr", "en_us");

  // Reset translation state to disable translations
  translationState.lang_cur = {};
  translationState.lang_disabled = true;

  const { lang_orig_text } = translationState;
  const items = document.getElementsByClassName('ds-i18n');
  for(let item of items) {
    $(item).html(lang_orig_text[item.id]);
  };
  $("#authorMsg").html("");
  $("#curLang").html("English");
  document.title = lang_orig_text[".title"];
}

function lang_set_direction(new_direction, lang_name) {
  const lang_prefix = lang_name.split("_")[0]
  $("html").attr("lang", lang_prefix);

  if(new_direction == translationState.lang_cur_direction)
    return;

  if(new_direction == "rtl") {
    $('#bootstrap-css').attr('integrity', 'sha384-dpuaG1suU0eT09tx5plTaGMLBsfDLzUCCUXOY2j/LSvXYuG6Bqs43ALlhIqAJVRb');
    $('#bootstrap-css').attr('href', 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.rtl.min.css');
  } else {
    $('#bootstrap-css').attr('integrity', 'sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH');
    $('#bootstrap-css').attr('href', 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css');
  }
  $("html").attr("dir", new_direction);
  translationState.lang_cur_direction = new_direction;
}

export function l(text) {
  if(!translationState || translationState.lang_disabled)
    return text;

  const [out] = translationState.lang_cur[text] || [];
  if(out) return out;
  
  console.log(`Missing translation for "${text}"`);
  return text;
}

function lang_translate(target_file, target_lang, target_direction) {
  return new Promise((resolve, reject) => {
    $.getJSON("lang/" + target_file)
      .done(function(data) {
        const { lang_orig_text, lang_cur } = translationState;
        lang_set_direction(target_direction, target_lang);

        $.each(data, function( key, val ) {
          if(lang_cur[key]) {
            console.log("Warn: already exists " + key);
          } else {
            lang_cur[key] = [val];
          }
        });

        if(Object.keys(lang_cur).length > 0) {
          translationState.lang_disabled = false;
        }

        const items = document.getElementsByClassName('ds-i18n');
        for(let item of items) {
          const originalText = lang_orig_text[item.id];
          const [translatedText] = lang_cur[originalText] || [];
          if (translatedText) {
            $(item).html(translatedText);
          } else {
            console.log(`Cannot find mapping for "${originalText}"`);
            $(item).html(originalText);
          }
        }

        const old_title = lang_orig_text[".title"];
        document.title = lang_cur[old_title];
        if(lang_cur[".authorMsg"]) {
          $("#authorMsg").html(lang_cur[".authorMsg"]);
        }
        $("#curLang").html(available_langs[target_lang]["name"]);

        resolve();
      })
      .fail(function(jqxhr, textStatus, error) {
        console.error("Failed to load translation file:", target_file, error);
        reject(error);
      });
  });
}

// Make lang_set available globally for onclick handlers in HTML
window.lang_set = lang_set;
