/**
 * Виджет amoCRM «AI-ассистент продаж» для правой панели карточки сделки (lcard-1).
 *
 * Менеджер нажимает «Сгенерировать рекомендации». Виджет вызывает бэкенд через
 * this.$authorizedAjax(): amoCRM добавляет заголовок X-Auth-Token с одноразовым
 * JWT, бэкенд проверяет его секретным ключом интеграции.
 *
 * Виджет ничего не отправляет клиенту: менеджер копирует ответ в чат сам.
 * Текст модели выводится только через .text()/.val() — без вставки HTML.
 */
define(['jquery'], function ($) {
  'use strict';

  var NS = 'aiSalesAssistant';
  var ROOT = '.ai-sa';

  return function () {
    var self = this;
    var phrase = '';

    function backendUrl() {
      var settings = self.get_settings() || {};
      return String(settings.backend_url || '').trim().replace(/\/+$/, '');
    }

    function currentLeadId() {
      var app = window.APP || window.AMOCRM;
      // Вне карточки current_card === false, у несохранённой сделки id === 0
      if (!app || !app.data || !app.data.current_card) return 0;
      return Number(app.data.current_card.id) || 0;
    }

    function panelHtml() {
      return [
        '<div class="ai-sa">',
        '  <label class="ai-sa__label">Сообщение клиента</label>',
        '  <textarea class="ai-sa__input ai-sa__message" rows="3" maxlength="4000"',
        '    placeholder="Пусто — возьмём последнее сообщение из чата сделки"></textarea>',
        '  <button type="button" class="ai-sa__btn ai-sa__btn--primary ai-sa__generate">Сгенерировать рекомендации</button>',
        '  <div class="ai-sa__status" hidden></div>',
        '  <div class="ai-sa__result" hidden>',
        '    <div class="ai-sa__warnings" hidden><b>Проверьте перед отправкой:</b><ul></ul></div>',
        '    <div class="ai-sa__block ai-sa__block--client">',
        '      <div class="ai-sa__title">Ответ клиенту</div>',
        '      <textarea class="ai-sa__input ai-sa__reply" rows="6"></textarea>',
        '      <button type="button" class="ai-sa__btn" data-ai-copy="reply">Копировать ответ</button>',
        '    </div>',
        '    <div class="ai-sa__block ai-sa__block--manager">',
        '      <div class="ai-sa__title">Подсказка менеджеру <span class="ai-sa__badge">не отправлять клиенту</span></div>',
        '      <div class="ai-sa__upsell-status"></div>',
        '      <div class="ai-sa__row ai-sa__product-row"><span class="ai-sa__key">Предложить:</span> <span class="ai-sa__product"></span></div>',
        '      <div class="ai-sa__row"><span class="ai-sa__key ai-sa__reason-label">Почему:</span> <span class="ai-sa__reason"></span></div>',
        '      <div class="ai-sa__phrase-block">',
        '        <div class="ai-sa__key">Пример фразы:</div>',
        '        <div class="ai-sa__phrase"></div>',
        '        <button type="button" class="ai-sa__btn" data-ai-copy="phrase">Копировать фразу</button>',
        '      </div>',
        '    </div>',
        '  </div>',
        '</div>'
      ].join('');
    }

    function status(text, isError) {
      var $s = $(ROOT + ' .ai-sa__status');
      $s.text(text || '').toggleClass('ai-sa__status--error', !!isError);
      $s.prop('hidden', !text);
    }

    function render(data) {
      var s = data.suggestion;
      var warnings = (data.meta && data.meta.warnings) || [];
      var $r = $(ROOT + ' .ai-sa__result');

      $r.find('.ai-sa__reply').val(s.customer_reply);

      var $list = $r.find('.ai-sa__warnings ul').empty();
      $.each(warnings, function (_, w) { $list.append($('<li>').text(w)); });
      $r.find('.ai-sa__warnings').prop('hidden', warnings.length === 0);

      if (s.upsell_applicable) {
        phrase = s.suggested_sales_phrase || '';
        $r.find('.ai-sa__upsell-status').text('Допродажа уместна').attr('data-ok', '1');
        $r.find('.ai-sa__product').text(s.upsell_recommendation || '—');
        $r.find('.ai-sa__reason-label').text('Почему:');
        $r.find('.ai-sa__phrase').text(phrase);
        $r.find('.ai-sa__product-row').prop('hidden', false);
        $r.find('.ai-sa__phrase-block').prop('hidden', !phrase);
      } else {
        phrase = '';
        $r.find('.ai-sa__upsell-status').text('Допродажа сейчас неуместна').attr('data-ok', '0');
        $r.find('.ai-sa__reason-label').text('Причина:');
        $r.find('.ai-sa__product-row, .ai-sa__phrase-block').prop('hidden', true);
      }
      $r.find('.ai-sa__reason').text(s.upsell_reason || '—');
      $r.prop('hidden', false);
    }

    function errorText(xhr) {
      if (xhr && xhr.responseJSON && xhr.responseJSON.error) return xhr.responseJSON.error.message;
      if (xhr && xhr.status === 0) return 'Сервер ассистента недоступен: проверьте адрес в настройках виджета и CORS.';
      return 'Ошибка сервера ассистента' + (xhr && xhr.status ? ' (' + xhr.status + ')' : '') + '.';
    }

    function generate() {
      var leadId = currentLeadId();
      var url = backendUrl();
      if (!url) return status('Укажите адрес сервера в настройках виджета.', true);
      if (!leadId) return status('Сначала сохраните сделку.', true);

      var $btn = $(ROOT + ' .ai-sa__generate').prop('disabled', true);
      var message = $.trim($(ROOT + ' .ai-sa__message').val());
      $(ROOT + ' .ai-sa__result').prop('hidden', true);
      status('Анализирую переписку…');

      self.$authorizedAjax({
        url: url + '/api/v1/amocrm/suggest',
        method: 'POST',
        contentType: 'application/json',
        dataType: 'json',
        timeout: 90000,
        data: JSON.stringify({ lead_id: leadId, message: message || null })
      })
        .done(function (data) { status(''); render(data); })
        .fail(function (xhr) { status(errorText(xhr), true); })
        .always(function () { $btn.prop('disabled', false); });
    }

    function copy(text) {
      if (!text) return;
      var done = function () { status('Скопировано — вставьте в чат и отправьте.'); };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, function () { status('Не удалось скопировать.', true); });
        return;
      }
      var $tmp = $('<textarea>').val(text).css({ position: 'fixed', opacity: 0 }).appendTo('body');
      $tmp[0].select();
      try { document.execCommand('copy'); done(); } catch (e) { status('Не удалось скопировать.', true); }
      $tmp.remove();
    }

    this.callbacks = {
      render: function () {
        if (self.system().area !== 'lcard') return true;
        self.render_template({
          caption: { class_name: 'ai-sa-caption' },
          body: '',
          render: panelHtml()
        });
        return true;
      },
      init: function () {
        var href = self.params.path + '/style.css?v=' + self.get_version();
        if (!$('link[href="' + href + '"]').length) {
          $('head').append('<link type="text/css" rel="stylesheet" href="' + href + '">');
        }
        return true;
      },
      bind_actions: function () {
        $(document)
          .off('.' + NS)
          .on('click.' + NS, ROOT + ' .ai-sa__generate', generate)
          .on('click.' + NS, ROOT + ' [data-ai-copy]', function () {
            copy($(this).attr('data-ai-copy') === 'reply' ? $(ROOT + ' .ai-sa__reply').val() : phrase);
          });
        return true;
      },
      settings: function () { return true; },
      onSave: function () { return true; },
      destroy: function () { $(document).off('.' + NS); }
    };

    return this;
  };
});
