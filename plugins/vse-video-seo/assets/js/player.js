/**
 * VSE Video SEO — Interactive YouTube Chapters Player Script
 *
 * Handles clicking on chapter timestamps (`[data-vse-seek]`, `.vse-chapter[data-time]`)
 * to seek the embedded YouTube iframe via postMessage (`seekTo`) or fallback `src` update
 * with `start=X&autoplay=1`.
 */
(function () {
    'use strict';

    function findYouTubeIframe() {
        return document.querySelector(
            'iframe[src*="youtube.com/embed"], iframe[src*="youtube-nocookie.com/embed"], iframe[data-src*="youtube.com/embed"]'
        );
    }

    function ensureJsApiEnabled(iframe) {
        if (!iframe) return;
        var src = iframe.getAttribute('src') || '';
        if (src && src.indexOf('enablejsapi=1') === -1) {
            var sep = src.indexOf('?') > -1 ? '&' : '?';
            iframe.setAttribute('src', src + sep + 'enablejsapi=1');
        }
    }

    function seekYouTubeVideo(seconds) {
        var sec = parseInt(seconds, 10);
        if (isNaN(sec) || sec < 0) return;

        var iframe = findYouTubeIframe();
        if (!iframe) return;

        var src = iframe.getAttribute('src') || '';

        // If iframe already has enablejsapi=1 and contentWindow is accessible, send YT command
        if (iframe.contentWindow && src.indexOf('enablejsapi=1') !== -1) {
            try {
                iframe.contentWindow.postMessage(
                    JSON.stringify({
                        event: 'command',
                        func: 'seekTo',
                        args: [sec, true]
                    }),
                    '*'
                );
                iframe.contentWindow.postMessage(
                    JSON.stringify({
                        event: 'command',
                        func: 'playVideo',
                        args: []
                    }),
                    '*'
                );
            } catch (err) {
                fallbackUpdateSrc(iframe, src, sec);
            }
        } else {
            fallbackUpdateSrc(iframe, src, sec);
        }

        if (typeof iframe.scrollIntoView === 'function') {
            iframe.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function fallbackUpdateSrc(iframe, src, seconds) {
        if (!src) return;
        var cleanUrl = src
            .replace(/([?&])start=\d+&?/g, '$1')
            .replace(/([?&])autoplay=\d+&?/g, '$1')
            .replace(/[?&]+$/, '');
        var sep = cleanUrl.indexOf('?') > -1 ? '&' : '?';
        var extra = cleanUrl.indexOf('enablejsapi=1') === -1 ? '&enablejsapi=1' : '';
        iframe.setAttribute('src', cleanUrl + sep + 'start=' + seconds + '&autoplay=1' + extra);
    }

    function initVsePlayer() {
        var iframe = findYouTubeIframe();
        if (iframe) {
            ensureJsApiEnabled(iframe);
        }

        // Expose global helper compatible with VSE injected articles
        window.vseSeek = seekYouTubeVideo;

        // Delegate clicks on [data-vse-seek] and .vse-chapter
        document.addEventListener('click', function (e) {
            var target = e.target.closest('[data-vse-seek], .vse-chapter');
            if (!target) return;

            var seekVal = target.getAttribute('data-vse-seek') || target.getAttribute('data-time');
            if (seekVal === null || seekVal === '') return;

            e.preventDefault();

            // Highlight active chapter item
            document.querySelectorAll('[data-vse-seek].is-active, .vse-chapter.is-active').forEach(function (el) {
                el.classList.remove('is-active');
            });
            target.classList.add('is-active');

            seekYouTubeVideo(seekVal);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVsePlayer);
    } else {
        initVsePlayer();
    }
})();
