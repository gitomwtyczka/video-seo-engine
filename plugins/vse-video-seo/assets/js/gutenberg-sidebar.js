/**
 * VSE Video SEO — Gutenberg Sidebar & Document Setting Panel
 *
 * Uses native WordPress global packages (wp.plugins, wp.editPost, wp.element,
 * wp.components, wp.data, wp.apiFetch) — zero external build step required.
 */
(function (wp) {
    'use strict';

    if (!wp || !wp.plugins || !wp.editPost || !wp.element || !wp.components || !wp.data) {
        return;
    }

    var registerPlugin = wp.plugins.registerPlugin;
    var PluginSidebar = wp.editPost.PluginSidebar;
    var PluginSidebarMoreMenuItem = wp.editPost.PluginSidebarMoreMenuItem;
    var PluginDocumentSettingPanel = wp.editPost.PluginDocumentSettingPanel;
    var el = wp.element.createElement;
    var Fragment = wp.element.Fragment;
    var useState = wp.element.useState;
    var useEffect = wp.element.useEffect;
    var useSelect = wp.data.useSelect;
    var useDispatch = wp.data.useDispatch;
    var apiFetch = wp.apiFetch;

    var PanelBody = wp.components.PanelBody;
    var TextControl = wp.components.TextControl;
    var Button = wp.components.Button;
    var Notice = wp.components.Notice;
    var Spinner = wp.components.Spinner;
    var ExternalLink = wp.components.ExternalLink;

    var cfg = window.vseEditorConfig || {};

    function getScoreColor(score) {
        if (score >= 80) return '#16a34a';
        if (score >= 50) return '#d97706';
        return '#dc2626';
    }

    function formatDuration(seconds) {
        var s = parseInt(seconds, 10) || 0;
        var h = Math.floor(s / 3600);
        var m = Math.floor((s % 3600) / 60);
        var rem = s % 60;
        var mm = m < 10 && h > 0 ? '0' + m : String(m);
        var ss = rem < 10 ? '0' + rem : String(rem);
        return h > 0 ? h + ':' + mm + ':' + ss : mm + ':' + ss;
    }

    function VseSidebarContent() {
        var postData = useSelect(function (select) {
            var editor = select('core/editor');
            if (!editor) return { postId: 0, postTitle: '', meta: {} };
            return {
                postId: editor.getCurrentPostId() || 0,
                postTitle: editor.getEditedPostAttribute('title') || '',
                meta: editor.getEditedPostAttribute('meta') || {}
            };
        }, []);

        var editPost = useDispatch('core/editor').editPost;

        var initialUrl = (postData.meta && postData.meta._vse_video_url) || '';
        var initialScore = (postData.meta && postData.meta._vse_seo_score) || 0;
        var hasSavedSchema = Boolean(postData.meta && postData.meta._vse_schema_json);

        var _urlState = useState(initialUrl);
        var videoUrl = _urlState[0];
        var setVideoUrl = _urlState[1];

        var _loadingPreview = useState(false);
        var isPreviewLoading = _loadingPreview[0];
        var setPreviewLoading = _loadingPreview[1];

        var _loadingInject = useState(false);
        var isInjectLoading = _loadingInject[0];
        var setInjectLoading = _loadingInject[1];

        var _previewData = useState(null);
        var previewData = _previewData[0];
        var setPreviewData = _previewData[1];

        var _injectResult = useState(null);
        var injectResult = _injectResult[0];
        var setInjectResult = _injectResult[1];

        var _errorMsg = useState('');
        var errorMsg = _errorMsg[0];
        var setErrorMsg = _errorMsg[1];

        var _upgradeUrl = useState('');
        var upgradeUrl = _upgradeUrl[0];
        var setUpgradeUrl = _upgradeUrl[1];

        useEffect(function () {
            if (!videoUrl && initialUrl) {
                setVideoUrl(initialUrl);
            }
        }, [initialUrl]);

        function handleAnalyzePreview() {
            if (!videoUrl || !videoUrl.trim()) {
                setErrorMsg('Wklej link do filmu YouTube (np. https://www.youtube.com/watch?v=...).');
                return;
            }
            setErrorMsg('');
            setUpgradeUrl('');
            setPreviewLoading(true);

            apiFetch({
                url: cfg.restUrl + 'preview',
                method: 'POST',
                headers: { 'X-WP-Nonce': cfg.nonce },
                data: {
                    video_url: videoUrl.trim(),
                    post_id: postData.postId
                }
            })
                .then(function (res) {
                    setPreviewLoading(false);
                    setPreviewData(res);
                    if (editPost) {
                        editPost({
                            meta: {
                                _vse_video_url: videoUrl.trim(),
                                _vse_seo_score: hasSavedSchema
                                    ? (res.after_score || 94)
                                    : (res.before_score || 28)
                            }
                        });
                    }
                })
                .catch(function (err) {
                    setPreviewLoading(false);
                    var detail = (err && (err.detail || err.message)) || 'Nie udało się pobrać podglądu wideo.';
                    setErrorMsg(detail);
                });
        }

        function handleInjectSchema() {
            if (!videoUrl || !videoUrl.trim()) {
                setErrorMsg('Najpierw wklej link do filmu YouTube.');
                return;
            }
            setErrorMsg('');
            setUpgradeUrl('');
            setInjectLoading(true);

            apiFetch({
                url: cfg.restUrl + 'inject-data',
                method: 'POST',
                headers: { 'X-WP-Nonce': cfg.nonce },
                data: {
                    video_url: videoUrl.trim(),
                    post_id: postData.postId,
                    post_title: postData.postTitle
                }
            })
                .then(function (res) {
                    setInjectLoading(false);
                    setInjectResult(res);

                    var schemaStr = typeof res.schema_json === 'string'
                        ? res.schema_json
                        : JSON.stringify(res.schema_json || []);
                    var chaptersStr = JSON.stringify(res.chapters || []);
                    var newScore = res.after_score || 94;

                    if (editPost) {
                        editPost({
                            meta: {
                                _vse_video_url: videoUrl.trim(),
                                _vse_schema_json: schemaStr,
                                _vse_chapters_json: chaptersStr,
                                _vse_seo_score: newScore
                            }
                        });
                    }
                })
                .catch(function (err) {
                    setInjectLoading(false);
                    var detail = (err && (err.detail || err.message)) || 'Błąd podczas generowania Schema JSON-LD.';
                    setErrorMsg(detail);
                    if (err && err.upgrade_url) {
                        setUpgradeUrl(err.upgrade_url);
                    } else if (detail.indexOf('limit') !== -1 || detail.indexOf('plan') !== -1) {
                        setUpgradeUrl(cfg.dashboardUrl || 'https://vse.impresjapr.pl/dashboard');
                    }
                });
        }

        function insertChaptersBlockToEditor() {
            var chapters = (injectResult && injectResult.chapters) ||
                (previewData && previewData.rich_result && previewData.rich_result.key_moments) || [];
            if (!chapters.length || !wp.blocks || !wp.data.dispatch('core/block-editor')) {
                return;
            }
            var itemsHtml = chapters.map(function (ch) {
                var sec = ch.time || ch.start_seconds || 0;
                var timeLabel = formatDuration(sec);
                var label = ch.label || ch.title || 'Rozdział';
                return '<li><a href="#vse-player" class="vse-chapter" data-vse-seek="' + sec + '" data-time="' + sec + '">' +
                    '<span class="vse-chapter-time">' + timeLabel + '</span> ' +
                    '<span>' + label + '</span></a></li>';
            }).join('\n');

            var blockHtml = '<div class="vse-chapters-box">' +
                '<p class="vse-chapters-title">🎬 Rozdziały wideo (kliknij, aby przewinąć):</p>' +
                '<ul class="vse-chapters-list">' + itemsHtml + '</ul></div>';

            var block = wp.blocks.createBlock('core/html', { content: blockHtml });
            wp.data.dispatch('core/block-editor').insertBlocks(block);
        }

        var currentScore = injectResult
            ? (injectResult.after_score || 94)
            : previewData
                ? (hasSavedSchema ? (previewData.after_score || 94) : (previewData.before_score || 28))
                : initialScore;

        var targetScore = (previewData && previewData.after_score) || 94;

        return el(
            Fragment,
            null,
            // API Key Warning if not configured
            !cfg.hasApiKey && el(
                PanelBody,
                { title: '⚠️ Konfiguracja klucza API', initialOpen: true },
                el(
                    'p',
                    { style: { fontSize: '12px', color: '#475569', margin: '0 0 8px 0' } },
                    'Aby wstrzykiwać pełne Schema JSON-LD + Meta SEO (5 filmów/mies. za darmo), połącz darmowy klucz API.'
                ),
                el(
                    Button,
                    {
                        isSecondary: true,
                        href: cfg.settingsUrl,
                        style: { width: '100%', justifyContent: 'center' }
                    },
                    'Ustaw klucz VSE API →'
                )
            ),

            // Step 1: Analyze Video URL
            el(
                PanelBody,
                { title: '🎬 1. Analiza Video SEO', initialOpen: true },
                el(TextControl, {
                    label: 'Link do filmu YouTube',
                    placeholder: 'https://www.youtube.com/watch?v=...',
                    value: videoUrl,
                    onChange: function (val) { setVideoUrl(val); }
                }),
                el(
                    Button,
                    {
                        isPrimary: true,
                        isBusy: isPreviewLoading,
                        disabled: isPreviewLoading || isInjectLoading,
                        onClick: handleAnalyzePreview,
                        style: {
                            width: '100%',
                            justifyContent: 'center',
                            background: '#0f172a',
                            borderColor: '#0f172a',
                            marginBottom: '8px'
                        }
                    },
                    isPreviewLoading ? 'Analizowanie filmu...' : 'Analizuj Video SEO (Score + Rich Result)'
                ),

                errorMsg && el(
                    Notice,
                    { status: 'error', isDismissible: true, onRemove: function () { setErrorMsg(''); } },
                    el('div', null, errorMsg),
                    upgradeUrl && el(
                        'div',
                        { style: { marginTop: '6px' } },
                        el(
                            ExternalLink,
                            { href: upgradeUrl },
                            'Zwiększ limit w panelu VSE →'
                        )
                    )
                ),

                // Video SEO Score Bar
                (currentScore > 0 || previewData) && el(
                    'div',
                    {
                        style: {
                            background: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            borderRadius: '8px',
                            padding: '12px',
                            marginTop: '10px'
                        }
                    },
                    el(
                        'div',
                        { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' } },
                        el('span', { style: { fontSize: '12px', fontWeight: 600, color: '#334155' } }, 'Video SEO Score'),
                        el(
                            'span',
                            { style: { fontSize: '14px', fontWeight: 700, color: getScoreColor(currentScore) } },
                            currentScore + ' / 100'
                        )
                    ),
                    el(
                        'div',
                        { style: { width: '100%', height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' } },
                        el('div', {
                            style: {
                                width: Math.min(100, Math.max(5, currentScore)) + '%',
                                height: '100%',
                                background: getScoreColor(currentScore),
                                transition: 'width 0.3s ease'
                            }
                        })
                    ),
                    !hasSavedSchema && !injectResult && el(
                        'p',
                        { style: { fontSize: '11px', color: '#475569', margin: '8px 0 0 0' } },
                        '🚀 Po wstrzyknięciu VSE Schema (VideoObject + Clip + FAQPage) Twój wpis osiągnie ',
                        el('strong', { style: { color: '#16a34a' } }, targetScore + '/100 pkt'),
                        '!'
                    ),
                    (hasSavedSchema || injectResult) && el(
                        'p',
                        { style: { fontSize: '11px', color: '#16a34a', margin: '8px 0 0 0', fontWeight: 600 } },
                        '✓ Czyste Schema JSON-LD aktywne w <head> (ominięto wp_kses_post)'
                    )
                ),

                // Google Video Rich Result Preview Card
                previewData && previewData.rich_result && el(
                    'div',
                    {
                        style: {
                            marginTop: '12px',
                            border: '1px solid #cbd5e1',
                            borderRadius: '8px',
                            padding: '10px',
                            background: '#ffffff'
                        }
                    },
                    el(
                        'div',
                        { style: { fontSize: '10px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '6px' } },
                        'Podgląd Google Video Rich Result'
                    ),
                    el(
                        'div',
                        { style: { position: 'relative', borderRadius: '6px', overflow: 'hidden', marginBottom: '8px', background: '#000' } },
                        previewData.rich_result.thumbnail_url && el('img', {
                            src: previewData.rich_result.thumbnail_url,
                            alt: previewData.rich_result.title || '',
                            style: { width: '100%', height: 'auto', display: 'block' }
                        }),
                        el(
                            'span',
                            {
                                style: {
                                    position: 'absolute',
                                    bottom: '6px',
                                    right: '6px',
                                    background: 'rgba(0,0,0,0.82)',
                                    color: '#fff',
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    padding: '2px 6px',
                                    borderRadius: '4px'
                                }
                            },
                            '▶ ' + formatDuration(previewData.rich_result.duration_seconds || 0)
                        ),
                        el(
                            'span',
                            {
                                style: {
                                    position: 'absolute',
                                    top: '6px',
                                    left: '6px',
                                    background: '#2563eb',
                                    color: '#fff',
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    padding: '2px 6px',
                                    borderRadius: '4px'
                                }
                            },
                            'KEY MOMENTS (Clip Schema)'
                        )
                    ),
                    el(
                        'div',
                        { style: { fontSize: '13px', fontWeight: 600, color: '#1a0dab', lineHeight: 1.3, marginBottom: '4px' } },
                        previewData.rich_result.title || postData.postTitle
                    ),
                    el(
                        'div',
                        { style: { fontSize: '11px', color: '#475569' } },
                        'Kanał: ' + (previewData.rich_result.channel_title || 'YouTube') +
                        ' • Est. rozdziałów AI: ' + (previewData.rich_result.estimated_clips || 5)
                    ),
                    previewData.rich_result.recommendation && el(
                        'div',
                        { style: { fontSize: '11px', color: '#0f172a', background: '#fef3c7', padding: '6px 8px', borderRadius: '4px', marginTop: '8px' } },
                        '💡 ' + previewData.rich_result.recommendation
                    )
                )
            ),

            // Step 2: Inject JSON-LD Schema + SEO Meta
            el(
                PanelBody,
                { title: '⚡ 2. Wstrzyknij Schema + Meta SEO', initialOpen: true },
                el(
                    'p',
                    { style: { fontSize: '12px', color: '#475569', marginTop: 0 } },
                    'Generuje VideoObject + Clip (Key Moments) + FAQPage JSON-LD do <head> oraz ustawia Title, Description i Focus Keyword w ',
                    el('strong', null, cfg.activeAdapter || 'RankMath / Yoast / SEOPress'),
                    '.'
                ),
                el(
                    Button,
                    {
                        isPrimary: true,
                        isBusy: isInjectLoading,
                        disabled: isInjectLoading || isPreviewLoading,
                        onClick: handleInjectSchema,
                        style: {
                            width: '100%',
                            justifyContent: 'center',
                            background: '#e11d48',
                            borderColor: '#e11d48',
                            fontWeight: 600
                        }
                    },
                    isInjectLoading
                        ? 'Generowanie AI Schema (ok. 15-30s)...'
                        : 'Wstrzyknij Schema JSON-LD + Meta SEO'
                ),
                el(
                    'p',
                    { style: { fontSize: '11px', color: '#64748b', textAlign: 'center', margin: '6px 0 0 0' } },
                    'Darmowy limit: 5 filmów / mies. w planie Free.'
                ),

                injectResult && el(
                    'div',
                    {
                        style: {
                            marginTop: '12px',
                            background: '#f0fdf4',
                            border: '1px solid #bbf7d0',
                            borderRadius: '8px',
                            padding: '10px'
                        }
                    },
                    el(
                        'div',
                        { style: { fontWeight: 700, color: '#166534', fontSize: '12px', marginBottom: '6px' } },
                        '✓ Wstrzyknięto Schema JSON-LD i zaktualizowano Meta SEO!'
                    ),
                    injectResult.seo_title && el(
                        'div',
                        { style: { fontSize: '11px', color: '#1e293b', marginBottom: '4px' } },
                        el('strong', null, 'SEO Title: '),
                        injectResult.seo_title
                    ),
                    injectResult.focus_keyword && el(
                        'div',
                        { style: { fontSize: '11px', color: '#1e293b', marginBottom: '4px' } },
                        el('strong', null, 'Focus Keyword: '),
                        injectResult.focus_keyword
                    ),
                    injectResult.chapters && injectResult.chapters.length > 0 && el(
                        Button,
                        {
                            isSecondary: true,
                            onClick: insertChaptersBlockToEditor,
                            style: { width: '100%', justifyContent: 'center', marginTop: '6px' }
                        },
                        '+ Wstaw interaktywny blok rozdziałów do treści'
                    )
                )
            ),

            // Step 3: Upsell Banner for VSE Pro / Agency
            el(
                PanelBody,
                { title: '🚀 Pełny Artykuł AI z Wideo (VSE Pro)', initialOpen: true },
                el(
                    'div',
                    {
                        style: {
                            background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
                            color: '#ffffff',
                            borderRadius: '8px',
                            padding: '14px'
                        }
                    },
                    el(
                        'span',
                        {
                            style: {
                                background: '#e11d48',
                                color: '#fff',
                                fontSize: '10px',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                textTransform: 'uppercase'
                            }
                        },
                        'VSE PRO / AGENCY'
                    ),
                    el(
                        'h4',
                        { style: { color: '#fff', margin: '8px 0 6px 0', fontSize: '14px' } },
                        'Chcesz wygenerować cały artykuł z tego filmu w 30 sekund?'
                    ),
                    el(
                        'ul',
                        { style: { margin: '0 0 12px 16px', padding: 0, fontSize: '11px', color: '#cbd5e1', lineHeight: 1.5 } },
                        el('li', null, 'Pełne artykuły eksperckie z transkrypcji AI'),
                        el('li', null, 'Automatyczne streszczenie TL;DR, cytaty i sekcja FAQ'),
                        el('li', null, 'Screenshoty z wideo (ImageObject) + integracja GSC'),
                        el('li', null, 'Auto-publikacja 1-klikiem na wiele portali WordPress')
                    ),
                    el(
                        'a',
                        {
                            href: cfg.registerUrl || 'https://vse.impresjapr.pl/register?utm_source=wp_plugin',
                            target: '_blank',
                            rel: 'noopener noreferrer',
                            style: {
                                display: 'block',
                                textAlign: 'center',
                                background: '#e11d48',
                                color: '#ffffff',
                                fontWeight: 700,
                                fontSize: '12px',
                                padding: '8px 12px',
                                borderRadius: '6px',
                                textDecoration: 'none'
                            }
                        },
                        'Wypróbuj VSE Pro / Załóż konto →'
                    )
                )
            )
        );
    }

    function VsePluginApp() {
        return el(
            Fragment,
            null,
            el(
                PluginSidebarMoreMenuItem,
                { target: 'vse-video-seo-sidebar', icon: 'video-alt3' },
                'VSE Video SEO'
            ),
            el(
                PluginSidebar,
                {
                    name: 'vse-video-seo-sidebar',
                    title: 'VSE Video SEO — AI Schema',
                    icon: 'video-alt3'
                },
                el(VseSidebarContent, null)
            ),
            el(
                PluginDocumentSettingPanel,
                {
                    name: 'vse-video-seo-doc-panel',
                    title: 'VSE Video SEO (Score & Schema)',
                    icon: 'video-alt3'
                },
                el(VseSidebarContent, null)
            )
        );
    }

    registerPlugin('vse-video-seo', {
        render: VsePluginApp,
        icon: 'video-alt3'
    });
})(window.wp);
