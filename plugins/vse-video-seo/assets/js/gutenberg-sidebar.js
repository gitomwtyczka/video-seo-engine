/**
 * VSE Video SEO v3.0.0 — Gutenberg Sidebar & Document Setting Panel
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
    var SelectControl = wp.components.SelectControl;
    var CheckboxControl = wp.components.CheckboxControl;
    var Button = wp.components.Button;
    var Notice = wp.components.Notice;
    var ExternalLink = wp.components.ExternalLink;

    var cfg = window.vseEditorConfig || {};

    var LANGUAGE_OPTIONS = [
        { label: '🇵🇱 Polski (pl)', value: 'pl' },
        { label: '🇬🇧 English (en)', value: 'en' },
        { label: '🇩🇪 Deutsch (de)', value: 'de' },
        { label: '🇪🇸 Español (es)', value: 'es' },
        { label: '🇫🇷 Français (fr)', value: 'fr' },
        { label: '🇮🇹 Italiano (it)', value: 'it' },
        { label: '🇺🇦 Українська (uk)', value: 'uk' },
        { label: '🇵🇹 Português (pt)', value: 'pt' }
    ];

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

        var _langState = useState('pl');
        var targetLang = _langState[0];
        var setTargetLang = _langState[1];

        var _autoInsertArticle = useState(true);
        var autoInsertArticle = _autoInsertArticle[0];
        var setAutoInsertArticle = _autoInsertArticle[1];

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

        var _historyItems = useState([]);
        var historyItems = _historyItems[0];
        var setHistoryItems = _historyItems[1];

        var _selectedHistoryId = useState('');
        var selectedHistoryId = _selectedHistoryId[0];
        var setSelectedHistoryId = _selectedHistoryId[1];

        var _loadingHistory = useState(false);
        var isHistoryLoading = _loadingHistory[0];
        var setHistoryLoading = _loadingHistory[1];

        var _importingHistory = useState(false);
        var isImportingHistory = _importingHistory[0];
        var setImportingHistory = _importingHistory[1];

        var _quotaInfo = useState(cfg.cachedStatus || {});
        var quotaInfo = _quotaInfo[0];
        var setQuotaInfo = _quotaInfo[1];

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

        function applyPackageToGutenberg(res, insertFullHtml) {
            var schemaStr = typeof res.schema_json === 'string'
                ? res.schema_json
                : JSON.stringify(res.schema_json || []);
            var chaptersStr = JSON.stringify(res.chapters || []);
            var newScore = res.after_score || res.seo_score || 96;
            var newTitle = res.post_title || res.seo_title || '';

            if (editPost) {
                var edits = {
                    meta: {
                        _vse_video_url: res.video_url || videoUrl.trim(),
                        _vse_schema_json: schemaStr,
                        _vse_chapters_json: chaptersStr,
                        _vse_seo_score: newScore
                    }
                };
                if (newTitle && (!postData.postTitle || !postData.postTitle.trim())) {
                    edits.title = newTitle;
                }
                editPost(edits);
            }

            if (insertFullHtml && res.assembled_html && wp.blocks && wp.data.dispatch('core/block-editor')) {
                var block = wp.blocks.createBlock('core/html', { content: res.assembled_html });
                wp.data.dispatch('core/block-editor').insertBlocks(block);
            }

            if (res.remaining_quota !== undefined || res.extra_quota_balance !== undefined) {
                setQuotaInfo(function (prev) {
                    return Object.assign({}, prev, {
                        plan: res.plan || prev.plan,
                        monthly_quota: res.monthly_quota !== undefined ? res.monthly_quota : prev.monthly_quota,
                        used_this_month: res.used_this_month !== undefined ? res.used_this_month : prev.used_this_month,
                        remaining_quota: res.remaining_quota !== undefined ? res.remaining_quota : prev.remaining_quota,
                        extra_quota_balance: res.extra_quota_balance !== undefined ? res.extra_quota_balance : prev.extra_quota_balance
                    });
                });
            }
        }

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
                                    ? (res.after_score || 96)
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

        function handleInjectFullPackage() {
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
                    post_title: postData.postTitle,
                    target_lang: targetLang,
                    lang: targetLang,
                    include_schema: true
                }
            })
                .then(function (res) {
                    setInjectLoading(false);
                    setInjectResult(res);
                    applyPackageToGutenberg(res, autoInsertArticle);
                })
                .catch(function (err) {
                    setInjectLoading(false);
                    var detail = (err && (err.detail || err.message)) || 'Błąd podczas generowania pakietu Video SEO.';
                    setErrorMsg(detail);
                    if (err && err.upgrade_url) {
                        setUpgradeUrl(err.upgrade_url);
                    } else if (detail.indexOf('limit') !== -1 || detail.indexOf('plan') !== -1) {
                        setUpgradeUrl(cfg.topupUrl || cfg.dashboardUrl || 'https://vse.impresjapr.pl/cennik#topup');
                    }
                });
        }

        function insertFullPackageToEditor() {
            if (!injectResult || !injectResult.assembled_html || !wp.blocks || !wp.data.dispatch('core/block-editor')) {
                return;
            }
            var newTitle = injectResult.post_title || injectResult.seo_title || '';
            if (editPost && newTitle && (!postData.postTitle || !postData.postTitle.trim())) {
                editPost({ title: newTitle });
            }
            var block = wp.blocks.createBlock('core/html', { content: injectResult.assembled_html });
            wp.data.dispatch('core/block-editor').insertBlocks(block);
        }

        function insertChaptersBlockToEditor() {
            var chapters = (injectResult && injectResult.chapters) ||
                (previewData && previewData.rich_result && previewData.rich_result.key_moments) || [];
            if (!chapters.length || !wp.blocks || !wp.data.dispatch('core/block-editor')) {
                return;
            }
            var itemsHtml = chapters.map(function (ch) {
                var sec = ch.time || ch.start_seconds || 0;
                var timeLabel = ch.timestamp || formatDuration(sec);
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

        function handleLoadHistory() {
            setHistoryLoading(true);
            setErrorMsg('');
            apiFetch({
                url: cfg.restUrl + 'history?limit=25',
                method: 'GET',
                headers: { 'X-WP-Nonce': cfg.nonce }
            })
                .then(function (res) {
                    setHistoryLoading(false);
                    var items = (res && res.items) || (Array.isArray(res) ? res : []);
                    setHistoryItems(items);
                    if (items.length > 0 && !selectedHistoryId) {
                        setSelectedHistoryId(String(items[0].job_id || items[0].id));
                    }
                })
                .catch(function (err) {
                    setHistoryLoading(false);
                    setErrorMsg((err && (err.detail || err.message)) || 'Nie udało się pobrać historii z VSE.');
                });
        }

        function handleImportHistoryItem() {
            if (!selectedHistoryId) {
                setErrorMsg('Wybierz materiał z listy historii VSE.');
                return;
            }
            setErrorMsg('');
            setImportingHistory(true);

            apiFetch({
                url: cfg.restUrl + 'import-history-item',
                method: 'POST',
                headers: { 'X-WP-Nonce': cfg.nonce },
                data: {
                    job_id: selectedHistoryId,
                    post_id: postData.postId,
                    create_new: false,
                    mode: 'editor_only',
                    include_schema: true
                }
            })
                .then(function (res) {
                    setImportingHistory(false);
                    setInjectResult(res);
                    if (res.video_url) {
                        setVideoUrl(res.video_url);
                    }
                    applyPackageToGutenberg(res, true);
                })
                .catch(function (err) {
                    setImportingHistory(false);
                    setErrorMsg((err && (err.detail || err.message)) || 'Nie udało się zaimportować materiału z historii.');
                });
        }

        var currentScore = injectResult
            ? (injectResult.after_score || 96)
            : previewData
                ? (hasSavedSchema ? (previewData.after_score || 96) : (previewData.before_score || 28))
                : initialScore;

        var targetScore = (previewData && previewData.after_score) || 96;
        var planLabel = ((quotaInfo && quotaInfo.plan) || 'free').toUpperCase();
        var usedCount = (quotaInfo && quotaInfo.used_this_month) || 0;
        var monthlyMax = (quotaInfo && quotaInfo.monthly_quota !== undefined) ? quotaInfo.monthly_quota : 5;
        var extraBalance = (quotaInfo && quotaInfo.extra_quota_balance) || 0;

        var historySelectOptions = [{ label: '— Wybierz materiał z chmury VSE —', value: '' }].concat(
            historyItems.map(function (item) {
                var idVal = String(item.job_id || item.id);
                var dateStr = (item.created_at || '').slice(0, 10);
                var titleStr = item.post_title || item.seo_title || item.video_title || ('Materiał #' + idVal);
                return {
                    label: '[' + dateStr + ' | ' + (item.lang || 'pl').toUpperCase() + '] ' + titleStr,
                    value: idVal
                };
            })
        );

        return el(
            Fragment,
            null,
            // Quota & Top-Up Summary Strip
            el(
                'div',
                {
                    style: {
                        background: '#f8fafc',
                        borderBottom: '1px solid #e2e8f0',
                        padding: '10px 14px',
                        fontSize: '11px',
                        color: '#334155',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: '6px'
                    }
                },
                el('span', null, 'Plan: ', el('strong', null, planLabel), ' • Limit: ', el('strong', null, usedCount + '/' + (monthlyMax < 0 ? '∞' : monthlyMax))),
                el('span', { style: { color: '#2563eb', fontWeight: 700 } }, 'Top-Up: +' + extraBalance + ' filmów')
            ),

            // API Key Warning if not configured
            !cfg.hasApiKey && el(
                PanelBody,
                { title: '⚠️ Konfiguracja klucza API', initialOpen: true },
                el(
                    'p',
                    { style: { fontSize: '12px', color: '#475569', margin: '0 0 8px 0' } },
                    'Połącz darmowy klucz vse_live_... (5 filmów/mies. za darmo + auto-parowanie bez App Passwords).'
                ),
                el(
                    Button,
                    {
                        isSecondary: true,
                        href: cfg.settingsUrl,
                        style: { width: '100%', justifyContent: 'center' }
                    },
                    'Połącz klucz VSE API →'
                )
            ),

            // Step 1: Analyze Video URL & Target Language
            el(
                PanelBody,
                { title: '🎬 1. Analiza Wideo & Język', initialOpen: true },
                el(TextControl, {
                    label: 'Link do filmu YouTube',
                    placeholder: 'https://www.youtube.com/watch?v=...',
                    value: videoUrl,
                    onChange: function (val) { setVideoUrl(val); }
                }),
                el(SelectControl, {
                    label: 'Język docelowy (Artykuł + Schema)',
                    value: targetLang,
                    options: LANGUAGE_OPTIONS,
                    onChange: function (val) { setTargetLang(val); }
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
                    isPreviewLoading ? 'Analizowanie filmu...' : '🔍 Analizuj Video SEO (Score + Preview)'
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
                            'Dokup pakiet Top-Up / Zmień plan →'
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
                        '🚀 Po wstrzyknięciu VSE v3.0 Twój wpis osiągnie ',
                        el('strong', { style: { color: '#16a34a' } }, targetScore + '/100 pkt'),
                        '!'
                    ),
                    (hasSavedSchema || injectResult) && el(
                        'p',
                        { style: { fontSize: '11px', color: '#16a34a', margin: '8px 0 0 0', fontWeight: 600 } },
                        '✓ Czyste Schema JSON-LD aktywne w <head>'
                    )
                )
            ),

            // Step 2: Generate & Inject Full Package (Article + TL;DR + Chapters + FAQ + Schema)
            el(
                PanelBody,
                { title: '⚡ 2. Pełny Artykuł AI + Schema + Meta', initialOpen: true },
                el(CheckboxControl, {
                    label: 'Wstaw pełny artykuł HTML + TL;DR + Rozdziały + FAQ do edytora oraz zaktualizuj tytuł wpisu',
                    checked: autoInsertArticle,
                    onChange: function (val) { setAutoInsertArticle(val); }
                }),
                el(
                    Button,
                    {
                        isPrimary: true,
                        isBusy: isInjectLoading,
                        disabled: isInjectLoading || isPreviewLoading,
                        onClick: handleInjectFullPackage,
                        style: {
                            width: '100%',
                            justifyContent: 'center',
                            background: '#e11d48',
                            borderColor: '#e11d48',
                            fontWeight: 600
                        }
                    },
                    isInjectLoading
                        ? 'Generowanie pakietu AI (20-45s)...'
                        : '🚀 Wygeneruj Artykuł + Schema + Meta'
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
                        '✓ Zapisano Schema JSON-LD w <head> i Meta SEO!'
                    ),
                    injectResult.seo_title && el(
                        'div',
                        { style: { fontSize: '11px', color: '#1e293b', marginBottom: '4px' } },
                        el('strong', null, 'SEO Title: '),
                        injectResult.seo_title
                    ),
                    injectResult.assembled_html && el(
                        Button,
                        {
                            isSecondary: true,
                            onClick: insertFullPackageToEditor,
                            style: { width: '100%', justifyContent: 'center', marginTop: '6px' }
                        },
                        '+ Wstaw pełny artykuł HTML (TL;DR + Rozdziały + FAQ)'
                    ),
                    injectResult.chapters && injectResult.chapters.length > 0 && el(
                        Button,
                        {
                            isSecondary: true,
                            onClick: insertChaptersBlockToEditor,
                            style: { width: '100%', justifyContent: 'center', marginTop: '6px' }
                        },
                        '+ Wstaw same rozdziały Key Moments'
                    )
                )
            ),

            // Step 3: Pull from VSE Cloud History (0 credits)
            el(
                PanelBody,
                { title: '📥 3. Pobierz z historii VSE (0 kredytów)', initialOpen: true },
                el(
                    'p',
                    { style: { fontSize: '11px', color: '#475569', marginTop: 0 } },
                    'Wstaw gotowy artykuł, rozdziały i Schema wygenerowane wcześniej w chmurze VSE — bez zużycia limitu filmów.'
                ),
                el(
                    Button,
                    {
                        isSecondary: true,
                        isBusy: isHistoryLoading,
                        onClick: handleLoadHistory,
                        style: { width: '100%', justifyContent: 'center', marginBottom: '8px' }
                    },
                    isHistoryLoading ? 'Pobieranie listy...' : '🔄 Załaduj ostatnie generacje z VSE'
                ),
                historyItems.length > 0 && el(
                    Fragment,
                    null,
                    el(SelectControl, {
                        label: 'Wybierz materiał z chmury VSE',
                        value: selectedHistoryId,
                        options: historySelectOptions,
                        onChange: function (val) { setSelectedHistoryId(val); }
                    }),
                    el(
                        Button,
                        {
                            isPrimary: true,
                            isBusy: isImportingHistory,
                            disabled: isImportingHistory || !selectedHistoryId,
                            onClick: handleImportHistoryItem,
                            style: {
                                width: '100%',
                                justifyContent: 'center',
                                background: '#2563eb',
                                borderColor: '#2563eb',
                                fontWeight: 600
                            }
                        },
                        isImportingHistory ? 'Importowanie do edytora...' : '📥 Wstaw wybrany materiał (0 kredytów)'
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
                'VSE Video SEO v3.0'
            ),
            el(
                PluginSidebar,
                {
                    name: 'vse-video-seo-sidebar',
                    title: 'VSE Video SEO v3.0 — AI Hub',
                    icon: 'video-alt3'
                },
                el(VseSidebarContent, null)
            ),
            el(
                PluginDocumentSettingPanel,
                {
                    name: 'vse-video-seo-doc-panel',
                    title: 'VSE Video SEO v3.0 (Artykuł & Schema)',
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
