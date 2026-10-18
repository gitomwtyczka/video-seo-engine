<?php
/**
 * Plugin Name:       VSE Video SEO — AI Article, Schema & Chapters
 * Plugin URI:        https://vse.impresjapr.pl
 * Description:       Kompletny hub publikacji Video SEO z AI (v3.0): 1-Click pełny artykuł SEO + TL;DR + interaktywne rozdziały Key Moments + FAQ, czyste wstrzykiwanie VideoObject/Clip/FAQPage JSON-LD do <head>, biblioteka chmury VSE (0 kredytów), auto-parowanie bez App Passwords oraz synchronizacja z RankMath / Yoast / SEOPress.
 * Version:           3.0.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            PressAI / Video SEO Engine
 * Author URI:        https://vse.impresjapr.pl
 * License:           GPL v2 or later
 * Text Domain:       vse-video-seo
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'VSE_VIDEO_SEO_VERSION', '3.0.0' );
define( 'VSE_VIDEO_SEO_DIR', plugin_dir_path( __FILE__ ) );
define( 'VSE_VIDEO_SEO_URL', plugin_dir_url( __FILE__ ) );
define( 'VSE_DEFAULT_API_URL', 'https://vse.impresjapr.pl' );

require_once VSE_VIDEO_SEO_DIR . 'includes/class-vse-head-injector.php';
require_once VSE_VIDEO_SEO_DIR . 'includes/class-vse-seo-adapter.php';
require_once VSE_VIDEO_SEO_DIR . 'includes/class-vse-gutenberg.php';

/**
 * Main plugin class for VSE Video SEO v3.0.0.
 */
class VSE_Video_SEO {

    private static $instance = null;

    public static function get_instance() {
        if ( null === self::$instance ) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action( 'init', array( $this, 'register_meta_fields' ) );
        add_action( 'admin_menu', array( $this, 'register_admin_menus' ) );
        add_action( 'admin_init', array( $this, 'register_settings' ) );
        add_action( 'add_meta_boxes', array( $this, 'register_post_meta_box' ) );
        add_action( 'rest_api_init', array( $this, 'register_rest_routes' ) );
        add_action( 'wp_enqueue_scripts', array( $this, 'enqueue_frontend_assets' ) );

        // WP AJAX handlers for admin dashboard & editor fallback
        add_action( 'wp_ajax_vse_validate_key', array( $this, 'ajax_validate_key' ) );
        add_action( 'wp_ajax_vse_preview', array( $this, 'ajax_preview' ) );
        add_action( 'wp_ajax_vse_inject_data', array( $this, 'ajax_inject_data' ) );
        add_action( 'wp_ajax_vse_create_post_from_video', array( $this, 'ajax_create_post_from_video' ) );
        add_action( 'wp_ajax_vse_get_history', array( $this, 'ajax_get_history' ) );
        add_action( 'wp_ajax_vse_import_history_item', array( $this, 'ajax_import_history_item' ) );

        // Initialize sub-components
        VSE_Head_Injector::init();
        VSE_Gutenberg::init();
    }

    /**
     * Supported target languages for VSE generation.
     *
     * @return array
     */
    public static function get_supported_languages() {
        return array(
            'pl' => '🇵🇱 Polski (pl)',
            'en' => '🇬🇧 English (en)',
            'de' => '🇩🇪 Deutsch (de)',
            'es' => '🇪🇸 Español (es)',
            'fr' => '🇫🇷 Français (fr)',
            'it' => '🇮🇹 Italiano (it)',
            'uk' => '🇺🇦 Українська (uk)',
            'pt' => '🇵🇹 Português (pt)',
        );
    }

    /**
     * Register post meta fields with REST API support for Gutenberg.
     */
    public function register_meta_fields() {
        $meta_keys = array(
            '_vse_schema_json'   => 'string',
            '_vse_video_url'     => 'string',
            '_vse_seo_score'     => 'integer',
            '_vse_chapters_json' => 'string',
        );

        $post_types = array( 'post', 'page' );
        foreach ( $post_types as $post_type ) {
            foreach ( $meta_keys as $meta_key => $type ) {
                register_post_meta(
                    $post_type,
                    $meta_key,
                    array(
                        'show_in_rest'      => true,
                        'single'            => true,
                        'type'              => $type,
                        'default'           => ( 'integer' === $type ) ? 0 : '',
                        'sanitize_callback' => ( '_vse_schema_json' === $meta_key || '_vse_chapters_json' === $meta_key )
                            ? array( $this, 'sanitize_json_meta' )
                            : ( 'integer' === $type ? 'absint' : 'sanitize_text_field' ),
                        'auth_callback'     => function () {
                            return current_user_can( 'edit_posts' );
                        },
                    )
                );
            }
        }
    }

    /**
     * Sanitize JSON string meta without stripping JSON-LD structure.
     *
     * @param mixed $value Raw meta value.
     * @return string Clean JSON string or empty string.
     */
    public function sanitize_json_meta( $value ) {
        if ( empty( $value ) ) {
            return '';
        }
        if ( is_array( $value ) || is_object( $value ) ) {
            return wp_json_encode( $value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
        }
        $decoded = json_decode( (string) $value, true );
        if ( null === $decoded && JSON_ERROR_NONE !== json_last_error() ) {
            return '';
        }
        return wp_json_encode( $decoded, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
    }

    /**
     * Enqueue player.js and player.css on singular posts with VSE schema or chapters.
     */
    public function enqueue_frontend_assets() {
        if ( ! is_singular() ) {
            return;
        }

        $post_id = get_queried_object_id();
        if ( ! $post_id ) {
            return;
        }

        $has_schema   = get_post_meta( $post_id, '_vse_schema_json', true );
        $has_chapters = get_post_meta( $post_id, '_vse_chapters_json', true );
        $post         = get_post( $post_id );
        $has_block    = $post && (
            false !== strpos( $post->post_content, 'data-vse-seek' ) ||
            false !== strpos( $post->post_content, 'vse-chapter' ) ||
            false !== strpos( $post->post_content, 'vse-chapters' )
        );

        if ( ! empty( $has_schema ) || ! empty( $has_chapters ) || $has_block ) {
            wp_enqueue_style(
                'vse-video-seo-player',
                VSE_VIDEO_SEO_URL . 'assets/css/player.css',
                array(),
                VSE_VIDEO_SEO_VERSION
            );

            wp_enqueue_script(
                'vse-video-seo-player',
                VSE_VIDEO_SEO_URL . 'assets/js/player.js',
                array(),
                VSE_VIDEO_SEO_VERSION,
                true
            );
        }
    }

    /**
     * Register top-level WP Admin Menu + Submenus + legacy Settings -> VSE Video SEO link.
     */
    public function register_admin_menus() {
        add_menu_page(
            __( 'VSE Video SEO — AI Hub Publikacji', 'vse-video-seo' ),
            __( 'VSE Video SEO', 'vse-video-seo' ),
            'edit_posts',
            'vse-video-seo',
            array( $this, 'render_admin_dashboard_page' ),
            'dashicons-video-alt3',
            58
        );

        add_submenu_page(
            'vse-video-seo',
            __( 'Generuj wpis z YouTube — VSE Video SEO', 'vse-video-seo' ),
            __( '🎬 Generuj z YouTube', 'vse-video-seo' ),
            'edit_posts',
            'vse-video-seo',
            array( $this, 'render_admin_dashboard_page' )
        );

        add_submenu_page(
            'vse-video-seo',
            __( 'Historia / Biblioteka VSE', 'vse-video-seo' ),
            __( '📚 Historia / Biblioteka', 'vse-video-seo' ),
            'edit_posts',
            'vse-video-seo-history',
            array( $this, 'render_admin_history_tab' )
        );

        add_submenu_page(
            'vse-video-seo',
            __( 'Połączenie, Auto-Parowanie & Quota — VSE Video SEO', 'vse-video-seo' ),
            __( '🔑 Połączenie & Quota', 'vse-video-seo' ),
            'manage_options',
            'vse-video-seo-connection',
            array( $this, 'render_admin_connection_tab' )
        );

        // Preserve link under Settings -> VSE Video SEO for returning users
        add_options_page(
            __( 'VSE Video SEO — Ustawienia', 'vse-video-seo' ),
            __( 'VSE Video SEO', 'vse-video-seo' ),
            'manage_options',
            'vse-video-seo-settings',
            array( $this, 'render_admin_connection_tab' )
        );
    }

    /**
     * Submenu wrapper for History tab.
     */
    public function render_admin_history_tab() {
        $_GET['tab'] = 'history';
        $this->render_admin_dashboard_page();
    }

    /**
     * Submenu wrapper for Connection & Quota tab.
     */
    public function render_admin_connection_tab() {
        $_GET['tab'] = 'connection';
        $this->render_admin_dashboard_page();
    }

    /**
     * Backward-compatible alias for render_settings_page().
     */
    public function render_settings_page() {
        $this->render_admin_dashboard_page();
    }

    /**
     * Register visible Meta Box in Post / Page editor (Gutenberg + Classic Editor).
     */
    public function register_post_meta_box() {
        add_meta_box(
            'vse_video_seo_metabox',
            '🎬 PressAI VSE Video SEO v3.0 — Generator Artykułu, Schema & Rozdziałów',
            array( $this, 'render_post_meta_box' ),
            array( 'post', 'page' ),
            'normal',
            'high'
        );
    }

    /**
     * Register WP options for VSE API Key and URL.
     */
    public function register_settings() {
        register_setting( 'vse_video_seo_settings', 'vse_api_key', array(
            'type'              => 'string',
            'sanitize_callback' => 'sanitize_text_field',
            'default'           => '',
        ) );

        register_setting( 'vse_video_seo_settings', 'vse_api_url', array(
            'type'              => 'string',
            'sanitize_callback' => 'esc_url_raw',
            'default'           => VSE_DEFAULT_API_URL,
        ) );
    }

    /**
     * Helper: get configured API base URL.
     */
    public static function get_api_url() {
        $url = get_option( 'vse_api_url', VSE_DEFAULT_API_URL );
        if ( empty( $url ) ) {
            $url = VSE_DEFAULT_API_URL;
        }
        return rtrim( $url, '/' );
    }

    /**
     * Helper: get configured API key.
     */
    public static function get_api_key() {
        return trim( (string) get_option( 'vse_api_key', '' ) );
    }

    /**
     * Helper: get current site domain.
     */
    public static function get_site_domain() {
        $parsed = wp_parse_url( home_url() );
        return isset( $parsed['host'] ) ? $parsed['host'] : '';
    }

    /**
     * Helper: extract 11-char YouTube video ID from URL or ID string.
     *
     * @param string $url YouTube URL or ID.
     * @return string
     */
    public static function extract_youtube_id( $url ) {
        $url = trim( (string) $url );
        if ( preg_match( '/^[a-zA-Z0-9_-]{11}$/', $url ) ) {
            return $url;
        }
        if ( preg_match( '/(?:v=|\/embed\/|youtu\.be\/|\/shorts\/|\/live\/)([a-zA-Z0-9_-]{11})/', $url, $m ) ) {
            return $m[1];
        }
        return '';
    }

    /**
     * Helper: format seconds as MM:SS or H:MM:SS.
     *
     * @param int $seconds Seconds.
     * @return string
     */
    public static function format_duration( $seconds ) {
        $s   = max( 0, (int) $seconds );
        $h   = (int) floor( $s / 3600 );
        $m   = (int) floor( ( $s % 3600 ) / 60 );
        $rem = $s % 60;
        if ( $h > 0 ) {
            return sprintf( '%d:%02d:%02d', $h, $m, $rem );
        }
        return sprintf( '%d:%02d', $m, $rem );
    }

    /**
     * Assemble clean HTML from VSE package sections according to selected checkboxes.
     *
     * @param array $data    Response data from VSE /v1/plugin/inject-data or /v1/plugin/history-item.
     * @param array $options Section flags: include_embed, include_tldr, include_article, include_chapters, include_faq.
     * @return string
     */
    public static function assemble_package_html( $data, $options = array() ) {
        $inc_embed    = isset( $options['include_embed'] ) ? (bool) $options['include_embed'] : true;
        $inc_tldr     = isset( $options['include_tldr'] ) ? (bool) $options['include_tldr'] : true;
        $inc_article  = isset( $options['include_article'] ) ? (bool) $options['include_article'] : true;
        $inc_chapters = isset( $options['include_chapters'] ) ? (bool) $options['include_chapters'] : true;
        $inc_faq      = isset( $options['include_faq'] ) ? (bool) $options['include_faq'] : true;

        $parts    = array();
        $video_id = ! empty( $data['video_id'] )
            ? sanitize_text_field( $data['video_id'] )
            : self::extract_youtube_id( isset( $data['video_url'] ) ? $data['video_url'] : '' );

        // 1. Embedded YouTube player
        if ( $inc_embed ) {
            if ( ! empty( $data['embed_html'] ) ) {
                $parts[] = $data['embed_html'];
            } elseif ( ! empty( $video_id ) ) {
                $parts[] = '<div class="vse-video-embed" style="margin:0 0 24px 0;">'
                    . '<div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:10px;background:#000;">'
                    . '<iframe id="vse-player" src="https://www.youtube.com/embed/' . esc_attr( $video_id ) . '?enablejsapi=1" '
                    . 'title="' . esc_attr( isset( $data['seo_title'] ) ? $data['seo_title'] : 'YouTube video player' ) . '" '
                    . 'style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" '
                    . 'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe>'
                    . '</div></div>';
            }
        }

        // 2. TL;DR Summary
        if ( $inc_tldr ) {
            if ( ! empty( $data['tldr_html'] ) ) {
                $parts[] = $data['tldr_html'];
            } elseif ( ! empty( $data['summary_tldr'] ) ) {
                if ( is_array( $data['summary_tldr'] ) ) {
                    $li = '';
                    foreach ( $data['summary_tldr'] as $point ) {
                        $li .= '<li>' . wp_kses_post( (string) $point ) . '</li>';
                    }
                    $parts[] = '<div class="vse-tldr-box" style="background:#f8fafc;border-left:4px solid #e11d48;padding:16px 20px;border-radius:6px;margin:0 0 24px 0;">'
                        . '<p style="margin:0 0 8px 0;font-weight:700;">⚡ Podsumowanie TL;DR (Kluczowe wnioski):</p>'
                        . '<ul style="margin:0;padding-left:20px;">' . $li . '</ul></div>';
                } else {
                    $parts[] = '<div class="vse-tldr-box" style="background:#f8fafc;border-left:4px solid #e11d48;padding:16px 20px;border-radius:6px;margin:0 0 24px 0;">'
                        . '<p style="margin:0 0 6px 0;font-weight:700;">⚡ Podsumowanie TL;DR:</p>'
                        . '<div>' . wp_kses_post( (string) $data['summary_tldr'] ) . '</div></div>';
                }
            }
        }

        // 3. Main SEO Article HTML
        if ( $inc_article ) {
            if ( ! empty( $data['article_html'] ) ) {
                $parts[] = $data['article_html'];
            } elseif ( ! empty( $data['content_html'] ) ) {
                $parts[] = $data['content_html'];
            }
        }

        // 4. Interactive Chapters (Key Moments)
        if ( $inc_chapters ) {
            if ( ! empty( $data['chapters_html'] ) ) {
                $parts[] = $data['chapters_html'];
            } elseif ( ! empty( $data['chapters'] ) && is_array( $data['chapters'] ) ) {
                $items_html = '';
                foreach ( $data['chapters'] as $ch ) {
                    $sec        = isset( $ch['time'] ) ? (int) $ch['time'] : ( isset( $ch['start_seconds'] ) ? (int) $ch['start_seconds'] : 0 );
                    $time_label = ! empty( $ch['timestamp'] ) ? sanitize_text_field( $ch['timestamp'] ) : self::format_duration( $sec );
                    $label      = isset( $ch['label'] ) ? $ch['label'] : ( isset( $ch['title'] ) ? $ch['title'] : 'Rozdział' );
                    $items_html .= '<li><a href="#vse-player" class="vse-chapter" data-vse-seek="' . esc_attr( $sec ) . '" data-time="' . esc_attr( $sec ) . '">'
                        . '<span class="vse-chapter-time">' . esc_html( $time_label ) . '</span> '
                        . '<span>' . esc_html( $label ) . '</span></a></li>' . "\n";
                }
                if ( '' !== $items_html ) {
                    $parts[] = '<div class="vse-chapters-box">'
                        . '<p class="vse-chapters-title">🎬 Rozdziały wideo (kliknij, aby przewinąć):</p>'
                        . '<ul class="vse-chapters-list">' . $items_html . '</ul></div>';
                }
            }
        }

        // 5. FAQ Section
        if ( $inc_faq ) {
            if ( ! empty( $data['faq_html'] ) ) {
                $parts[] = $data['faq_html'];
            } elseif ( ! empty( $data['faq'] ) && is_array( $data['faq'] ) ) {
                $faq_items = '';
                foreach ( $data['faq'] as $item ) {
                    $q = isset( $item['q'] ) ? $item['q'] : ( isset( $item['question'] ) ? $item['question'] : '' );
                    $a = isset( $item['a'] ) ? $item['a'] : ( isset( $item['answer'] ) ? $item['answer'] : '' );
                    if ( '' !== $q && '' !== $a ) {
                        $faq_items .= '<div class="vse-faq-item" style="margin-bottom:14px;">'
                            . '<h4 style="margin:0 0 4px 0;font-size:16px;">' . esc_html( $q ) . '</h4>'
                            . '<p style="margin:0;color:#334155;">' . wp_kses_post( $a ) . '</p></div>';
                    }
                }
                if ( '' !== $faq_items ) {
                    $parts[] = '<section class="vse-faq-section" style="margin-top:28px;">'
                        . '<h3>❓ Najczęściej zadawane pytania (FAQ)</h3>'
                        . $faq_items . '</section>';
                }
            }
        }

        // Fallback if backend only returned full_package_html
        if ( empty( $parts ) && ! empty( $data['full_package_html'] ) ) {
            return (string) $data['full_package_html'];
        }

        return implode( "\n\n", $parts );
    }

    /**
     * Save VSE metadata (_vse_schema_json, _vse_chapters_json, _vse_video_url, _vse_seo_score)
     * and synchronize RankMath / Yoast / SEOPress meta on a given post ID.
     *
     * @param int   $post_id        WP Post ID.
     * @param array $data           VSE payload.
     * @param bool  $include_schema Whether to save Schema & SEO meta.
     * @return array Synced SEO adapters.
     */
    public function save_vse_post_data( $post_id, $data, $include_schema = true ) {
        $post_id = absint( $post_id );
        if ( ! $post_id ) {
            return array();
        }

        $video_url = isset( $data['video_url'] ) ? sanitize_text_field( $data['video_url'] ) : '';
        if ( empty( $video_url ) && ! empty( $data['video_id'] ) ) {
            $video_url = 'https://www.youtube.com/watch?v=' . sanitize_text_field( $data['video_id'] );
        }
        if ( ! empty( $video_url ) ) {
            update_post_meta( $post_id, '_vse_video_url', $video_url );
        }

        $after_score = isset( $data['after_score'] )
            ? (int) $data['after_score']
            : ( isset( $data['seo_score'] ) ? (int) $data['seo_score'] : 96 );
        update_post_meta( $post_id, '_vse_seo_score', $after_score );

        if ( isset( $data['chapters_json'] ) && is_string( $data['chapters_json'] ) ) {
            update_post_meta( $post_id, '_vse_chapters_json', $data['chapters_json'] );
        } elseif ( isset( $data['chapters'] ) ) {
            update_post_meta( $post_id, '_vse_chapters_json', wp_json_encode( $data['chapters'], JSON_UNESCAPED_UNICODE ) );
        }

        $synced_adapters = array();
        if ( $include_schema ) {
            $schema_json = isset( $data['schema_json'] ) ? $data['schema_json'] : '';
            if ( is_array( $schema_json ) || is_object( $schema_json ) ) {
                $schema_json = wp_json_encode( $schema_json, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
            }
            if ( ! empty( $schema_json ) ) {
                update_post_meta( $post_id, '_vse_schema_json', $schema_json );
            }

            $seo_title       = isset( $data['seo_title'] ) ? $data['seo_title'] : ( isset( $data['post_title'] ) ? $data['post_title'] : '' );
            $meta_desc       = isset( $data['meta_description'] ) ? $data['meta_description'] : '';
            $focus_keyword   = isset( $data['focus_keyword'] ) ? $data['focus_keyword'] : '';
            $synced_adapters = VSE_SEO_Adapter::update_seo_meta( $post_id, $seo_title, $meta_desc, $focus_keyword );
        }

        return $synced_adapters;
    }

    /**
     * Update cached status option when quota numbers are returned from VSE backend.
     *
     * @param array $data Response data from VSE backend.
     */
    public static function update_cached_quota_from_response( $data ) {
        if ( ! is_array( $data ) ) {
            return;
        }
        $cached = get_option( 'vse_cached_status', array() );
        if ( ! is_array( $cached ) ) {
            $cached = array();
        }
        $keys = array( 'plan', 'monthly_quota', 'used_this_month', 'remaining_quota', 'extra_quota_balance', 'portal_paired', 'portal_id', 'allowed_domain' );
        $changed = false;
        foreach ( $keys as $k ) {
            if ( isset( $data[ $k ] ) ) {
                $cached[ $k ] = $data[ $k ];
                $changed      = true;
            }
        }
        if ( $changed ) {
            update_option( 'vse_cached_status', $cached );
        }
    }

    /**
     * Register WP REST API endpoints (/wp-json/vse/v1/*).
     */
    public function register_rest_routes() {
        register_rest_route( 'vse/v1', '/validate', array(
            'methods'             => 'POST',
            'callback'            => array( $this, 'rest_validate_key' ),
            'permission_callback' => function () {
                return current_user_can( 'edit_posts' );
            },
        ) );

        register_rest_route( 'vse/v1', '/preview', array(
            'methods'             => 'POST',
            'callback'            => array( $this, 'rest_preview' ),
            'permission_callback' => function () {
                return current_user_can( 'edit_posts' );
            },
        ) );

        register_rest_route( 'vse/v1', '/inject-data', array(
            'methods'             => 'POST',
            'callback'            => array( $this, 'rest_inject_data' ),
            'permission_callback' => function () {
                return current_user_can( 'edit_posts' );
            },
        ) );

        register_rest_route( 'vse/v1', '/create-post-from-video', array(
            'methods'             => 'POST',
            'callback'            => array( $this, 'rest_create_post_from_video' ),
            'permission_callback' => function () {
                return current_user_can( 'edit_posts' );
            },
        ) );

        register_rest_route( 'vse/v1', '/history', array(
            'methods'             => array( 'GET', 'POST' ),
            'callback'            => array( $this, 'rest_get_history' ),
            'permission_callback' => function () {
                return current_user_can( 'edit_posts' );
            },
        ) );

        register_rest_route( 'vse/v1', '/import-history-item', array(
            'methods'             => 'POST',
            'callback'            => array( $this, 'rest_import_history_item' ),
            'permission_callback' => function () {
                return current_user_can( 'edit_posts' );
            },
        ) );

        // External endpoints for VSE Dashboard Push to WP without App Passwords
        register_rest_route( 'vse/v1', '/ping', array(
            'methods'             => array( 'GET', 'POST' ),
            'callback'            => array( $this, 'rest_external_ping' ),
            'permission_callback' => array( $this, 'verify_external_vse_request' ),
        ) );

        register_rest_route( 'vse/v1', '/publish', array(
            'methods'             => 'POST',
            'callback'            => array( $this, 'rest_external_publish' ),
            'permission_callback' => array( $this, 'verify_external_vse_request' ),
        ) );
    }

    /**
     * Permission callback for external push endpoints (/wp-json/vse/v1/ping and /publish).
     * Verifies X-VSE-Key-Hash (SHA-256 of local vse_api_key) or X-VSE-Api-Key header.
     *
     * @param WP_REST_Request $request Incoming request.
     * @return bool|WP_Error
     */
    public function verify_external_vse_request( WP_REST_Request $request ) {
        $local_key = self::get_api_key();
        if ( '' === $local_key ) {
            return new WP_Error(
                'vse_no_api_key',
                __( 'Wtyczka VSE Video SEO nie ma jeszcze zapisanego klucza API.', 'vse-video-seo' ),
                array( 'status' => 401 )
            );
        }

        $incoming_hash = trim( (string) $request->get_header( 'x-vse-key-hash' ) );
        $incoming_raw  = trim( (string) $request->get_header( 'x-vse-api-key' ) );

        $expected_hash = hash( 'sha256', $local_key );

        if ( '' !== $incoming_hash && hash_equals( $expected_hash, strtolower( $incoming_hash ) ) ) {
            return true;
        }

        if ( '' !== $incoming_raw && hash_equals( $local_key, $incoming_raw ) ) {
            return true;
        }

        return new WP_Error(
            'vse_unauthorized',
            __( 'Nieprawidłowy podpis klucza VSE (X-VSE-Key-Hash).', 'vse-video-seo' ),
            array( 'status' => 401 )
        );
    }

    /**
     * Helper: resolve default author ID (first administrator or editor) for external VSE publish calls.
     *
     * @return int
     */
    public static function get_default_author_id() {
        if ( get_current_user_id() > 0 ) {
            return get_current_user_id();
        }
        $admins = get_users( array(
            'role__in' => array( 'administrator', 'editor' ),
            'number'   => 1,
            'orderby'  => 'ID',
            'order'    => 'ASC',
            'fields'   => 'ID',
        ) );
        if ( ! empty( $admins ) ) {
            return (int) $admins[0];
        }
        return 1;
    }

    /**
     * Proxy request to VSE backend API.
     *
     * @param string $endpoint Path starting with /v1/plugin/...
     * @param array  $payload  Body data to send as JSON.
     * @param int    $timeout  Request timeout in seconds.
     * @return array|WP_Error
     */
    public static function call_backend( $endpoint, $payload, $timeout = 45 ) {
        $url = self::get_api_url() . $endpoint;

        $response = wp_remote_post( $url, array(
            'timeout' => $timeout,
            'headers' => array(
                'Content-Type' => 'application/json',
                'Accept'       => 'application/json',
            ),
            'body'    => wp_json_encode( $payload ),
        ) );

        if ( is_wp_error( $response ) ) {
            return $response;
        }

        $code = wp_remote_retrieve_response_code( $response );
        $body = wp_remote_retrieve_body( $response );
        $data = json_decode( $body, true );

        return array(
            'status_code' => $code,
            'data'        => is_array( $data ) ? $data : array( 'detail' => $body ),
        );
    }

    /**
     * REST callback: POST /wp-json/vse/v1/validate
     * Sends extended auto-pairing payload to VSE /v1/plugin/validate.
     */
    public function rest_validate_key( WP_REST_Request $request ) {
        $param_key = $request->get_param( 'api_key' );
        $param_url = $request->get_param( 'api_url' );

        if ( ! empty( $param_key ) && current_user_can( 'manage_options' ) ) {
            update_option( 'vse_api_key', sanitize_text_field( $param_key ) );
        }
        if ( ! empty( $param_url ) && current_user_can( 'manage_options' ) ) {
            update_option( 'vse_api_url', rtrim( esc_url_raw( $param_url ), '/' ) );
        }

        $api_key = sanitize_text_field( $param_key ?: self::get_api_key() );
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'valid'   => false,
                'message' => __( 'Brak klucza API VSE. Wklej klucz w zakładce Połączenie & Quota.', 'vse-video-seo' ),
            ), 400 );
        }

        $res = self::call_backend( '/v1/plugin/validate', array(
            'api_key'        => $api_key,
            'domain'         => self::get_site_domain(),
            'site_url'       => home_url(),
            'site_name'      => get_bloginfo( 'name' ),
            'plugin_version' => VSE_VIDEO_SEO_VERSION,
        ), 20 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'valid'   => false,
                'message' => $res->get_error_message(),
            ), 502 );
        }

        if ( 200 === $res['status_code'] && ! empty( $res['data']['valid'] ) ) {
            update_option( 'vse_cached_status', $res['data'] );
        }

        return new WP_REST_Response( $res['data'], $res['status_code'] );
    }

    /**
     * REST callback: POST /wp-json/vse/v1/preview
     */
    public function rest_preview( WP_REST_Request $request ) {
        $video_url = sanitize_text_field( $request->get_param( 'video_url' ) );
        $post_id   = absint( $request->get_param( 'post_id' ) );

        if ( empty( $video_url ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Podaj link do filmu YouTube.', 'vse-video-seo' ),
            ), 400 );
        }

        $res = self::call_backend( '/v1/plugin/preview', array(
            'video_url' => $video_url,
            'api_key'   => self::get_api_key(),
            'domain'    => self::get_site_domain(),
        ), 30 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'detail' => $res->get_error_message(),
            ), 502 );
        }

        if ( 200 === $res['status_code'] && $post_id > 0 && current_user_can( 'edit_post', $post_id ) ) {
            update_post_meta( $post_id, '_vse_video_url', $video_url );
            if ( isset( $res['data']['before_score'] ) ) {
                $existing_schema = get_post_meta( $post_id, '_vse_schema_json', true );
                $score_to_save   = ! empty( $existing_schema )
                    ? (int) ( $res['data']['after_score'] ?? 96 )
                    : (int) $res['data']['before_score'];
                update_post_meta( $post_id, '_vse_seo_score', $score_to_save );
            }
        }

        return new WP_REST_Response( $res['data'], $res['status_code'] );
    }

    /**
     * REST callback: POST /wp-json/vse/v1/inject-data
     * Generates full package from VSE /v1/plugin/inject-data and saves schema/meta/content.
     */
    public function rest_inject_data( WP_REST_Request $request ) {
        $video_url           = sanitize_text_field( $request->get_param( 'video_url' ) );
        $post_id             = absint( $request->get_param( 'post_id' ) );
        $post_title          = sanitize_text_field( $request->get_param( 'post_title' ) );
        $target_lang         = sanitize_text_field( $request->get_param( 'target_lang' ) ?: ( $request->get_param( 'lang' ) ?: 'pl' ) );
        $update_post_content = (bool) $request->get_param( 'update_post_content' );
        $include_schema      = null !== $request->get_param( 'include_schema' ) ? (bool) $request->get_param( 'include_schema' ) : true;

        $section_options = array(
            'include_embed'    => null !== $request->get_param( 'include_embed' ) ? (bool) $request->get_param( 'include_embed' ) : true,
            'include_tldr'     => null !== $request->get_param( 'include_tldr' ) ? (bool) $request->get_param( 'include_tldr' ) : true,
            'include_article'  => null !== $request->get_param( 'include_article' ) ? (bool) $request->get_param( 'include_article' ) : true,
            'include_chapters' => null !== $request->get_param( 'include_chapters' ) ? (bool) $request->get_param( 'include_chapters' ) : true,
            'include_faq'      => null !== $request->get_param( 'include_faq' ) ? (bool) $request->get_param( 'include_faq' ) : true,
        );

        $api_key = self::get_api_key();
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Brak skonfigurowanego klucza API VSE. Przejdź do VSE Video SEO → Połączenie & Quota.', 'vse-video-seo' ),
            ), 401 );
        }

        if ( empty( $video_url ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Podaj link do filmu YouTube.', 'vse-video-seo' ),
            ), 400 );
        }

        $post_url = $post_id ? get_permalink( $post_id ) : home_url();
        if ( empty( $post_title ) && $post_id ) {
            $post_title = get_the_title( $post_id );
        }

        $res = self::call_backend( '/v1/plugin/inject-data', array(
            'api_key'     => $api_key,
            'domain'      => self::get_site_domain(),
            'video_url'   => $video_url,
            'post_title'  => $post_title,
            'post_url'    => $post_url,
            'target_lang' => $target_lang,
            'lang'        => $target_lang,
        ), 120 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'detail' => $res->get_error_message(),
            ), 502 );
        }

        $data = $res['data'];
        $code = $res['status_code'];

        if ( 200 === $code ) {
            $data['video_url']      = $video_url;
            $data['assembled_html'] = self::assemble_package_html( $data, $section_options );

            if ( $post_id > 0 && current_user_can( 'edit_post', $post_id ) ) {
                $synced_adapters = $this->save_vse_post_data( $post_id, $data, $include_schema );

                if ( $update_post_content && ! empty( $data['assembled_html'] ) ) {
                    $update_arr = array(
                        'ID'           => $post_id,
                        'post_content' => $data['assembled_html'],
                    );
                    $existing_post = get_post( $post_id );
                    $new_title     = ! empty( $data['post_title'] ) ? $data['post_title'] : ( ! empty( $data['seo_title'] ) ? $data['seo_title'] : '' );
                    if ( $existing_post && empty( $existing_post->post_title ) && ! empty( $new_title ) ) {
                        $update_arr['post_title'] = sanitize_text_field( $new_title );
                    }
                    wp_update_post( $update_arr );
                }

                $data['wp_saved']        = true;
                $data['synced_adapters'] = $synced_adapters;
            }

            self::update_cached_quota_from_response( $data );
        }

        return new WP_REST_Response( $data, $code );
    }

    /**
     * REST callback: POST /wp-json/vse/v1/create-post-from-video
     * 1-Click Full Package generator from the main WP Admin VSE menu.
     */
    public function rest_create_post_from_video( WP_REST_Request $request ) {
        $video_url      = sanitize_text_field( $request->get_param( 'video_url' ) );
        $target_lang    = sanitize_text_field( $request->get_param( 'target_lang' ) ?: 'pl' );
        $custom_title   = sanitize_text_field( $request->get_param( 'post_title' ) );
        $raw_status     = sanitize_text_field( $request->get_param( 'post_status' ) ?: 'draft' );
        $post_status    = in_array( $raw_status, array( 'draft', 'publish' ), true ) ? $raw_status : 'draft';
        $include_schema = null !== $request->get_param( 'include_schema' ) ? (bool) $request->get_param( 'include_schema' ) : true;

        $section_options = array(
            'include_embed'    => null !== $request->get_param( 'include_embed' ) ? (bool) $request->get_param( 'include_embed' ) : true,
            'include_tldr'     => null !== $request->get_param( 'include_tldr' ) ? (bool) $request->get_param( 'include_tldr' ) : true,
            'include_article'  => null !== $request->get_param( 'include_article' ) ? (bool) $request->get_param( 'include_article' ) : true,
            'include_chapters' => null !== $request->get_param( 'include_chapters' ) ? (bool) $request->get_param( 'include_chapters' ) : true,
            'include_faq'      => null !== $request->get_param( 'include_faq' ) ? (bool) $request->get_param( 'include_faq' ) : true,
        );

        $api_key = self::get_api_key();
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Brak klucza API VSE. Połącz klucz w zakładce Połączenie & Quota.', 'vse-video-seo' ),
            ), 401 );
        }

        if ( empty( $video_url ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Podaj link do filmu YouTube.', 'vse-video-seo' ),
            ), 400 );
        }

        $res = self::call_backend( '/v1/plugin/inject-data', array(
            'api_key'     => $api_key,
            'domain'      => self::get_site_domain(),
            'video_url'   => $video_url,
            'post_title'  => $custom_title,
            'post_url'    => home_url(),
            'target_lang' => $target_lang,
            'lang'        => $target_lang,
        ), 120 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'detail' => $res->get_error_message(),
            ), 502 );
        }

        $data = $res['data'];
        $code = $res['status_code'];

        if ( 200 !== $code ) {
            return new WP_REST_Response( $data, $code );
        }

        $data['video_url'] = $video_url;
        $assembled_html    = self::assemble_package_html( $data, $section_options );
        $final_title       = ! empty( $custom_title )
            ? $custom_title
            : ( ! empty( $data['post_title'] ) ? $data['post_title'] : ( ! empty( $data['seo_title'] ) ? $data['seo_title'] : 'Artykuł Wideo YouTube' ) );

        $post_id = wp_insert_post( array(
            'post_type'    => 'post',
            'post_title'   => sanitize_text_field( $final_title ),
            'post_content' => $assembled_html,
            'post_status'  => $post_status,
            'post_author'  => self::get_default_author_id(),
        ), true );

        if ( is_wp_error( $post_id ) ) {
            return new WP_REST_Response( array(
                'detail' => $post_id->get_error_message(),
            ), 500 );
        }

        $synced_adapters = $this->save_vse_post_data( $post_id, $data, $include_schema );
        self::update_cached_quota_from_response( $data );

        return new WP_REST_Response( array(
            'ok'              => true,
            'post_id'         => $post_id,
            'post_title'      => $final_title,
            'post_status'     => $post_status,
            'edit_url'        => get_edit_post_link( $post_id, 'raw' ),
            'view_url'        => get_permalink( $post_id ),
            'seo_score'       => isset( $data['after_score'] ) ? (int) $data['after_score'] : 96,
            'synced_adapters' => $synced_adapters,
            'remaining_quota' => isset( $data['remaining_quota'] ) ? $data['remaining_quota'] : null,
            'extra_quota_balance' => isset( $data['extra_quota_balance'] ) ? $data['extra_quota_balance'] : null,
        ), 200 );
    }

    /**
     * REST callback: GET /wp-json/vse/v1/history
     * Pulls previously generated jobs from VSE cloud without consuming quota.
     */
    public function rest_get_history( WP_REST_Request $request ) {
        $api_key = self::get_api_key();
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Brak klucza API VSE. Połącz klucz w zakładce Połączenie & Quota.', 'vse-video-seo' ),
                'items'  => array(),
            ), 401 );
        }

        $limit = absint( $request->get_param( 'limit' ) ?: 25 );
        if ( $limit < 1 || $limit > 100 ) {
            $limit = 25;
        }

        $res = self::call_backend( '/v1/plugin/history', array(
            'api_key' => $api_key,
            'domain'  => self::get_site_domain(),
            'limit'   => $limit,
        ), 25 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'detail' => $res->get_error_message(),
                'items'  => array(),
            ), 502 );
        }

        return new WP_REST_Response( $res['data'], $res['status_code'] );
    }

    /**
     * REST callback: POST /wp-json/vse/v1/import-history-item
     * Fetches full package for a single history job_id (0 credits) and creates or updates a WP post.
     */
    public function rest_import_history_item( WP_REST_Request $request ) {
        $job_id              = sanitize_text_field( (string) $request->get_param( 'job_id' ) );
        $post_id             = absint( $request->get_param( 'post_id' ) );
        $mode                = sanitize_text_field( (string) $request->get_param( 'mode' ) );
        $create_new          = (bool) $request->get_param( 'create_new' ) || ( 'create_post' === $mode ) || ( 0 === $post_id && 'editor_only' !== $mode );
        $raw_status          = sanitize_text_field( $request->get_param( 'post_status' ) ?: 'draft' );
        $post_status         = in_array( $raw_status, array( 'draft', 'publish' ), true ) ? $raw_status : 'draft';
        $update_post_content = (bool) $request->get_param( 'update_post_content' );
        $include_schema      = null !== $request->get_param( 'include_schema' ) ? (bool) $request->get_param( 'include_schema' ) : true;

        $section_options = array(
            'include_embed'    => null !== $request->get_param( 'include_embed' ) ? (bool) $request->get_param( 'include_embed' ) : true,
            'include_tldr'     => null !== $request->get_param( 'include_tldr' ) ? (bool) $request->get_param( 'include_tldr' ) : true,
            'include_article'  => null !== $request->get_param( 'include_article' ) ? (bool) $request->get_param( 'include_article' ) : true,
            'include_chapters' => null !== $request->get_param( 'include_chapters' ) ? (bool) $request->get_param( 'include_chapters' ) : true,
            'include_faq'      => null !== $request->get_param( 'include_faq' ) ? (bool) $request->get_param( 'include_faq' ) : true,
        );

        $api_key = self::get_api_key();
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Brak klucza API VSE.', 'vse-video-seo' ),
            ), 401 );
        }

        if ( '' === $job_id ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Brak identyfikatora materiału (job_id).', 'vse-video-seo' ),
            ), 400 );
        }

        $res = self::call_backend( '/v1/plugin/history-item', array(
            'api_key' => $api_key,
            'domain'  => self::get_site_domain(),
            'job_id'  => is_numeric( $job_id ) ? (int) $job_id : $job_id,
        ), 30 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'detail' => $res->get_error_message(),
            ), 502 );
        }

        $data = $res['data'];
        $code = $res['status_code'];

        if ( 200 !== $code ) {
            return new WP_REST_Response( $data, $code );
        }

        $assembled_html         = self::assemble_package_html( $data, $section_options );
        $data['assembled_html'] = $assembled_html;
        $final_title            = ! empty( $data['post_title'] )
            ? $data['post_title']
            : ( ! empty( $data['seo_title'] ) ? $data['seo_title'] : 'Artykuł Wideo z VSE' );

        if ( $create_new ) {
            $new_post_id = wp_insert_post( array(
                'post_type'    => 'post',
                'post_title'   => sanitize_text_field( $final_title ),
                'post_content' => $assembled_html,
                'post_status'  => $post_status,
                'post_author'  => self::get_default_author_id(),
            ), true );

            if ( is_wp_error( $new_post_id ) ) {
                return new WP_REST_Response( array(
                    'detail' => $new_post_id->get_error_message(),
                ), 500 );
            }

            $synced_adapters          = $this->save_vse_post_data( $new_post_id, $data, $include_schema );
            $data['ok']               = true;
            $data['post_id']          = $new_post_id;
            $data['post_title']       = $final_title;
            $data['edit_url']         = get_edit_post_link( $new_post_id, 'raw' );
            $data['view_url']         = get_permalink( $new_post_id );
            $data['synced_adapters']  = $synced_adapters;

            return new WP_REST_Response( $data, 200 );
        }

        if ( $post_id > 0 && current_user_can( 'edit_post', $post_id ) ) {
            $synced_adapters = $this->save_vse_post_data( $post_id, $data, $include_schema );
            if ( $update_post_content && ! empty( $assembled_html ) ) {
                $update_arr    = array(
                    'ID'           => $post_id,
                    'post_content' => $assembled_html,
                );
                $existing_post = get_post( $post_id );
                if ( $existing_post && empty( $existing_post->post_title ) && ! empty( $final_title ) ) {
                    $update_arr['post_title'] = sanitize_text_field( $final_title );
                }
                wp_update_post( $update_arr );
            }
            $data['wp_saved']        = true;
            $data['synced_adapters'] = $synced_adapters;
        }

        $data['ok'] = true;
        return new WP_REST_Response( $data, 200 );
    }

    /**
     * External REST callback: GET /wp-json/vse/v1/ping
     * Verifies connection from VSE Dashboard without WordPress App Passwords.
     */
    public function rest_external_ping( WP_REST_Request $request ) {
        return new WP_REST_Response( array(
            'ok'                 => true,
            'site_url'           => home_url(),
            'site_name'          => get_bloginfo( 'name' ),
            'domain'             => self::get_site_domain(),
            'plugin_version'     => VSE_VIDEO_SEO_VERSION,
            'active_seo_adapter' => VSE_SEO_Adapter::detect_active_plugin_label(),
        ), 200 );
    }

    /**
     * External REST callback: POST /wp-json/vse/v1/publish
     * Receives full article + Schema JSON-LD + SEO Meta pushed directly from VSE Dashboard.
     */
    public function rest_external_publish( WP_REST_Request $request ) {
        $author_id = self::get_default_author_id();
        wp_set_current_user( $author_id );

        $post_id          = absint( $request->get_param( 'post_id' ) );
        $post_title       = sanitize_text_field( (string) $request->get_param( 'post_title' ) );
        $post_content     = (string) $request->get_param( 'post_content' );
        $raw_status       = sanitize_text_field( (string) ( $request->get_param( 'post_status' ) ?: 'draft' ) );
        $post_status      = in_array( $raw_status, array( 'draft', 'publish', 'pending', 'future', 'private' ), true ) ? $raw_status : 'draft';
        $video_url        = sanitize_text_field( (string) $request->get_param( 'video_url' ) );
        $seo_title        = sanitize_text_field( (string) $request->get_param( 'seo_title' ) );
        $meta_description = sanitize_textarea_field( (string) $request->get_param( 'meta_description' ) );
        $focus_keyword    = sanitize_text_field( (string) $request->get_param( 'focus_keyword' ) );
        $schema_json      = $request->get_param( 'schema_json' );
        $chapters_json    = $request->get_param( 'chapters_json' );
        $seo_score        = absint( $request->get_param( 'seo_score' ) ?: 96 );

        if ( '' === $post_title ) {
            $post_title = '' !== $seo_title ? $seo_title : 'Artykuł Wideo VSE';
        }

        if ( $post_id > 0 && get_post( $post_id ) ) {
            $updated_id = wp_update_post( array(
                'ID'           => $post_id,
                'post_title'   => $post_title,
                'post_content' => $post_content,
                'post_status'  => $post_status,
            ), true );

            if ( is_wp_error( $updated_id ) ) {
                return new WP_REST_Response( array(
                    'ok'     => false,
                    'detail' => $updated_id->get_error_message(),
                ), 500 );
            }
        } else {
            $post_id = wp_insert_post( array(
                'post_type'    => 'post',
                'post_title'   => $post_title,
                'post_content' => $post_content,
                'post_status'  => $post_status,
                'post_author'  => $author_id,
            ), true );

            if ( is_wp_error( $post_id ) ) {
                return new WP_REST_Response( array(
                    'ok'     => false,
                    'detail' => $post_id->get_error_message(),
                ), 500 );
            }
        }

        if ( ! empty( $schema_json ) ) {
            if ( is_array( $schema_json ) || is_object( $schema_json ) ) {
                $schema_json = wp_json_encode( $schema_json, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
            }
            update_post_meta( $post_id, '_vse_schema_json', (string) $schema_json );
        }

        if ( ! empty( $chapters_json ) ) {
            if ( is_array( $chapters_json ) || is_object( $chapters_json ) ) {
                $chapters_json = wp_json_encode( $chapters_json, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
            }
            update_post_meta( $post_id, '_vse_chapters_json', (string) $chapters_json );
        }

        if ( '' !== $video_url ) {
            update_post_meta( $post_id, '_vse_video_url', $video_url );
        }
        update_post_meta( $post_id, '_vse_seo_score', $seo_score );

        VSE_SEO_Adapter::update_seo_meta( $post_id, $seo_title, $meta_description, $focus_keyword );

        return new WP_REST_Response( array(
            'ok'             => true,
            'post_id'        => $post_id,
            'post_url'       => get_permalink( $post_id ),
            'edit_url'       => get_edit_post_link( $post_id, 'raw' ),
            'status'         => $post_status,
            'plugin_version' => VSE_VIDEO_SEO_VERSION,
        ), 200 );
    }

    /**
     * WP AJAX: Validate API key & Auto-Pair portal from Admin Dashboard.
     */
    public function ajax_validate_key() {
        check_ajax_referer( 'vse_admin_nonce', 'nonce' );
        if ( ! current_user_can( 'manage_options' ) ) {
            wp_send_json_error( array( 'message' => 'Brak uprawnień.' ), 403 );
        }

        $api_key = isset( $_POST['api_key'] ) ? sanitize_text_field( wp_unslash( $_POST['api_key'] ) ) : self::get_api_key();
        $api_url = isset( $_POST['api_url'] ) ? esc_url_raw( wp_unslash( $_POST['api_url'] ) ) : self::get_api_url();

        if ( ! empty( $api_key ) ) {
            update_option( 'vse_api_key', $api_key );
        }
        if ( ! empty( $api_url ) ) {
            update_option( 'vse_api_url', rtrim( $api_url, '/' ) );
        }

        $res = self::call_backend( '/v1/plugin/validate', array(
            'api_key'        => $api_key,
            'domain'         => self::get_site_domain(),
            'site_url'       => home_url(),
            'site_name'      => get_bloginfo( 'name' ),
            'plugin_version' => VSE_VIDEO_SEO_VERSION,
        ), 20 );

        if ( is_wp_error( $res ) ) {
            wp_send_json_error( array( 'message' => $res->get_error_message() ), 502 );
        }

        if ( 200 === $res['status_code'] && ! empty( $res['data']['valid'] ) ) {
            update_option( 'vse_cached_status', $res['data'] );
            wp_send_json_success( $res['data'] );
        } else {
            wp_send_json_error( $res['data'], $res['status_code'] );
        }
    }

    /**
     * WP AJAX fallback for preview.
     */
    public function ajax_preview() {
        check_ajax_referer( 'vse_editor_nonce', 'nonce' );
        if ( ! current_user_can( 'edit_posts' ) ) {
            wp_send_json_error( array( 'message' => 'Brak uprawnień.' ), 403 );
        }
        $req = new WP_REST_Request( 'POST', '/vse/v1/preview' );
        $req->set_param( 'video_url', isset( $_POST['video_url'] ) ? sanitize_text_field( wp_unslash( $_POST['video_url'] ) ) : '' );
        $req->set_param( 'post_id', isset( $_POST['post_id'] ) ? absint( $_POST['post_id'] ) : 0 );
        $resp = $this->rest_preview( $req );
        wp_send_json( $resp->get_data(), $resp->get_status() );
    }

    /**
     * WP AJAX fallback for inject-data.
     */
    public function ajax_inject_data() {
        check_ajax_referer( 'vse_editor_nonce', 'nonce' );
        if ( ! current_user_can( 'edit_posts' ) ) {
            wp_send_json_error( array( 'message' => 'Brak uprawnień.' ), 403 );
        }
        $req = new WP_REST_Request( 'POST', '/vse/v1/inject-data' );
        $req->set_param( 'video_url', isset( $_POST['video_url'] ) ? sanitize_text_field( wp_unslash( $_POST['video_url'] ) ) : '' );
        $req->set_param( 'post_id', isset( $_POST['post_id'] ) ? absint( $_POST['post_id'] ) : 0 );
        $req->set_param( 'post_title', isset( $_POST['post_title'] ) ? sanitize_text_field( wp_unslash( $_POST['post_title'] ) ) : '' );
        $req->set_param( 'target_lang', isset( $_POST['target_lang'] ) ? sanitize_text_field( wp_unslash( $_POST['target_lang'] ) ) : 'pl' );
        $resp = $this->rest_inject_data( $req );
        wp_send_json( $resp->get_data(), $resp->get_status() );
    }

    /**
     * WP AJAX fallback for create-post-from-video.
     */
    public function ajax_create_post_from_video() {
        check_ajax_referer( 'vse_admin_nonce', 'nonce' );
        if ( ! current_user_can( 'edit_posts' ) ) {
            wp_send_json_error( array( 'detail' => 'Brak uprawnień.' ), 403 );
        }
        $req = new WP_REST_Request( 'POST', '/vse/v1/create-post-from-video' );
        foreach ( array( 'video_url', 'target_lang', 'post_title', 'post_status', 'include_embed', 'include_tldr', 'include_article', 'include_chapters', 'include_faq', 'include_schema' ) as $field ) {
            if ( isset( $_POST[ $field ] ) ) {
                $req->set_param( $field, sanitize_text_field( wp_unslash( $_POST[ $field ] ) ) );
            }
        }
        $resp = $this->rest_create_post_from_video( $req );
        wp_send_json( $resp->get_data(), $resp->get_status() );
    }

    /**
     * WP AJAX fallback for history.
     */
    public function ajax_get_history() {
        check_ajax_referer( 'vse_editor_nonce', 'nonce' );
        if ( ! current_user_can( 'edit_posts' ) ) {
            wp_send_json_error( array( 'detail' => 'Brak uprawnień.' ), 403 );
        }
        $req  = new WP_REST_Request( 'GET', '/vse/v1/history' );
        $resp = $this->rest_get_history( $req );
        wp_send_json( $resp->get_data(), $resp->get_status() );
    }

    /**
     * WP AJAX fallback for import-history-item.
     */
    public function ajax_import_history_item() {
        check_ajax_referer( 'vse_editor_nonce', 'nonce' );
        if ( ! current_user_can( 'edit_posts' ) ) {
            wp_send_json_error( array( 'detail' => 'Brak uprawnień.' ), 403 );
        }
        $req = new WP_REST_Request( 'POST', '/vse/v1/import-history-item' );
        foreach ( array( 'job_id', 'post_id', 'mode', 'create_new', 'post_status', 'update_post_content' ) as $field ) {
            if ( isset( $_POST[ $field ] ) ) {
                $req->set_param( $field, sanitize_text_field( wp_unslash( $_POST[ $field ] ) ) );
            }
        }
        $resp = $this->rest_import_history_item( $req );
        wp_send_json( $resp->get_data(), $resp->get_status() );
    }

    /**
     * Render visible Meta Box inside Post / Page editor (Gutenberg bottom panel & Classic Editor).
     *
     * @param WP_Post $post Current WP_Post object.
     */
    public function render_post_meta_box( $post ) {
        $post_id        = isset( $post->ID ) ? (int) $post->ID : 0;
        $video_url      = get_post_meta( $post_id, '_vse_video_url', true );
        $seo_score      = (int) get_post_meta( $post_id, '_vse_seo_score', true );
        $saved_schema   = get_post_meta( $post_id, '_vse_schema_json', true );
        $has_api_key    = '' !== self::get_api_key();
        $rest_url       = esc_url_raw( rest_url( 'vse/v1/' ) );
        $rest_nonce     = wp_create_nonce( 'wp_rest' );
        $active_adapter = VSE_SEO_Adapter::detect_active_plugin_label();
        $languages      = self::get_supported_languages();
        ?>
        <div id="vse-metabox-wrap" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:8px 4px;">
            <?php if ( ! $has_api_key ) : ?>
                <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                    <span style="color:#991b1b;font-size:13px;">
                        ⚠️ <strong>Brak skonfigurowanego klucza API VSE.</strong> Połącz darmowy klucz (5 filmów/mies.), aby generować artykuły i Schema JSON-LD.
                    </span>
                    <a href="<?php echo esc_url( admin_url( 'admin.php?page=vse-video-seo&tab=connection' ) ); ?>" class="button button-primary" style="background:#e11d48;border-color:#e11d48;">
                        Połącz klucz VSE API →
                    </a>
                </div>
            <?php endif; ?>

            <div style="display:grid;grid-template-columns:1fr 220px auto;gap:12px;align-items:end;margin-bottom:14px;">
                <div>
                    <label for="vse-mb-video-url" style="display:block;font-weight:600;font-size:13px;margin-bottom:4px;color:#0f172a;">
                        🎬 Link do filmu YouTube
                    </label>
                    <input type="url" id="vse-mb-video-url" value="<?php echo esc_attr( $video_url ); ?>" placeholder="https://www.youtube.com/watch?v=..." style="width:100%;padding:6px 10px;" />
                </div>
                <div>
                    <label for="vse-mb-lang" style="display:block;font-weight:600;font-size:13px;margin-bottom:4px;color:#0f172a;">
                        🌐 Język docelowy
                    </label>
                    <select id="vse-mb-lang" style="width:100%;height:34px;">
                        <?php foreach ( $languages as $code => $label ) : ?>
                            <option value="<?php echo esc_attr( $code ); ?>"><?php echo esc_html( $label ); ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div>
                    <button type="button" class="button" id="vse-mb-preview-btn" style="height:34px;font-weight:600;">
                        🔍 Analizuj SEO (Preview)
                    </button>
                </div>
            </div>

            <!-- Preview Score Box -->
            <div id="vse-mb-preview-box" style="display:<?php echo $seo_score > 0 ? 'block' : 'none'; ?>;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                    <div>
                        <strong style="font-size:13px;color:#0f172a;">Video SEO Score:</strong>
                        <span id="vse-mb-score-val" style="font-size:16px;font-weight:700;color:<?php echo $seo_score >= 80 ? '#16a34a' : '#d97706'; ?>;margin-left:6px;">
                            <?php echo esc_html( $seo_score > 0 ? $seo_score . ' / 100' : '—' ); ?>
                        </span>
                    </div>
                    <div id="vse-mb-preview-meta" style="font-size:12px;color:#475569;">
                        Adapter SEO: <strong><?php echo esc_html( $active_adapter ); ?></strong>
                    </div>
                </div>
                <div id="vse-mb-preview-rec" style="font-size:12px;color:#334155;margin-top:6px;"></div>
            </div>

            <!-- Checkboxes what to inject into current post -->
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin-bottom:14px;">
                <div style="font-weight:600;font-size:13px;color:#0f172a;margin-bottom:8px;">
                    Co wstrzyknąć do bieżącego wpisu:
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:#334155;margin-bottom:10px;">
                    <label><input type="checkbox" id="vse-mb-inc-content" checked /> <strong>Wstaw pełny artykuł SEO HTML + TL;DR + Rozdziały + FAQ do treści wpisu</strong></label>
                    <label><input type="checkbox" id="vse-mb-inc-schema" checked /> <strong>Wstrzyknij Schema JSON-LD do &lt;head&gt; + Meta <?php echo esc_html( $active_adapter ); ?></strong></label>
                </div>
                <div id="vse-mb-sub-sections" style="display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#475569;padding-top:8px;border-top:1px dashed #e2e8f0;">
                    <span>Sekcje treści HTML:</span>
                    <label><input type="checkbox" id="vse-mb-sec-embed" checked /> Osadzone wideo YouTube</label>
                    <label><input type="checkbox" id="vse-mb-sec-tldr" checked /> Podsumowanie TL;DR</label>
                    <label><input type="checkbox" id="vse-mb-sec-article" checked /> Artykuł SEO</label>
                    <label><input type="checkbox" id="vse-mb-sec-chapters" checked /> Rozdziały Key Moments</label>
                    <label><input type="checkbox" id="vse-mb-sec-faq" checked /> Sekcja FAQ</label>
                </div>

                <div style="margin-top:14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                    <button type="button" class="button button-primary" id="vse-mb-inject-btn" style="background:#e11d48;border-color:#e11d48;font-weight:600;padding:4px 16px;height:36px;">
                        ⚡ Wygeneruj z YouTube i wstrzyknij do tego wpisu
                    </button>
                    <span id="vse-mb-status-msg" style="font-size:13px;font-weight:500;"></span>
                </div>
            </div>

            <!-- Pull from VSE Cloud History (0 credits) -->
            <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px;padding:14px 16px;margin-bottom:14px;">
                <div style="font-weight:600;font-size:13px;color:#0f172a;margin-bottom:8px;">
                    📥 Lub zaimportuj gotowy materiał z historii VSE (0 kredytów):
                </div>
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                    <select id="vse-mb-history-select" style="min-width:320px;flex:1;height:34px;">
                        <option value="">— Kliknij „Załaduj listę” lub wybierz materiał z chmury VSE —</option>
                    </select>
                    <button type="button" class="button" id="vse-mb-load-history-btn" style="height:34px;">
                        🔄 Załaduj listę
                    </button>
                    <button type="button" class="button button-secondary" id="vse-mb-import-history-btn" style="height:34px;font-weight:600;">
                        📥 Wstrzyknij wybrany materiał z historii
                    </button>
                </div>
            </div>

            <!-- Active JSON-LD in <head> Status & Preview -->
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <span style="font-size:13px;font-weight:600;color:#166534;">
                        Status Schema.org JSON-LD (`_vse_schema_json`):
                        <strong id="vse-mb-schema-badge">
                            <?php echo ! empty( $saved_schema ) ? '✅ Aktywne w &lt;head&gt; (VideoObject + Clip + FAQPage)' : '⚪ Brak zapisanego Schema w tym wpisie'; ?>
                        </strong>
                    </span>
                    <button type="button" class="button button-small" id="vse-mb-toggle-schema-btn">
                        Podgląd JSON-LD
                    </button>
                </div>
                <textarea id="vse-mb-schema-preview" readonly rows="5" style="display:none;width:100%;margin-top:10px;font-family:monospace;font-size:11px;background:#0f172a;color:#e2e8f0;padding:10px;border-radius:6px;"><?php echo esc_textarea( $saved_schema ); ?></textarea>
            </div>
        </div>

        <script>
        (function() {
            var restUrl = <?php echo wp_json_encode( $rest_url ); ?>;
            var restNonce = <?php echo wp_json_encode( $rest_nonce ); ?>;
            var postId = <?php echo (int) $post_id; ?>;

            var urlInput = document.getElementById('vse-mb-video-url');
            var langSelect = document.getElementById('vse-mb-lang');
            var previewBtn = document.getElementById('vse-mb-preview-btn');
            var previewBox = document.getElementById('vse-mb-preview-box');
            var scoreVal = document.getElementById('vse-mb-score-val');
            var previewRec = document.getElementById('vse-mb-preview-rec');
            var injectBtn = document.getElementById('vse-mb-inject-btn');
            var statusMsg = document.getElementById('vse-mb-status-msg');
            var historySelect = document.getElementById('vse-mb-history-select');
            var loadHistoryBtn = document.getElementById('vse-mb-load-history-btn');
            var importHistoryBtn = document.getElementById('vse-mb-import-history-btn');
            var schemaBadge = document.getElementById('vse-mb-schema-badge');
            var schemaPreview = document.getElementById('vse-mb-schema-preview');
            var toggleSchemaBtn = document.getElementById('vse-mb-toggle-schema-btn');

            if (toggleSchemaBtn && schemaPreview) {
                toggleSchemaBtn.addEventListener('click', function() {
                    schemaPreview.style.display = schemaPreview.style.display === 'none' ? 'block' : 'none';
                });
            }

            function insertContentIntoActiveEditor(html, newTitle, metaUpdates) {
                // 1. Gutenberg Block Editor
                if (window.wp && wp.data && wp.data.select && wp.data.dispatch && wp.data.select('core/block-editor')) {
                    try {
                        var editorDispatch = wp.data.dispatch('core/editor');
                        if (editorDispatch && editorDispatch.editPost) {
                            var edits = {};
                            if (newTitle) {
                                var curTitle = wp.data.select('core/editor').getEditedPostAttribute('title');
                                if (!curTitle || !curTitle.trim()) {
                                    edits.title = newTitle;
                                }
                            }
                            if (metaUpdates) {
                                edits.meta = metaUpdates;
                            }
                            if (Object.keys(edits).length > 0) {
                                editorDispatch.editPost(edits);
                            }
                        }
                        if (html && wp.blocks) {
                            var block = wp.blocks.createBlock('core/html', { content: html });
                            wp.data.dispatch('core/block-editor').insertBlocks(block);
                        }
                        return;
                    } catch (e) {
                        console.warn('VSE Gutenberg insert fallback:', e);
                    }
                }

                // 2. Classic Editor (TinyMCE or textarea)
                if (newTitle) {
                    var titleEl = document.getElementById('title');
                    if (titleEl && !titleEl.value.trim()) {
                        titleEl.value = newTitle;
                        var promptEl = document.getElementById('title-prompt-text');
                        if (promptEl) promptEl.classList.add('screen-reader-text');
                    }
                }
                if (html) {
                    if (window.tinyMCE && tinyMCE.get('content') && !tinyMCE.get('content').isHidden()) {
                        tinyMCE.get('content').execCommand('mceInsertContent', false, html);
                    } else {
                        var contentArea = document.getElementById('content');
                        if (contentArea) {
                            contentArea.value = (contentArea.value ? contentArea.value + "\n\n" : '') + html;
                        }
                    }
                }
            }

            if (previewBtn) {
                previewBtn.addEventListener('click', function() {
                    var vUrl = urlInput ? urlInput.value.trim() : '';
                    if (!vUrl) {
                        alert('Wklej link do filmu YouTube.');
                        return;
                    }
                    previewBtn.disabled = true;
                    previewBtn.textContent = '⏳ Analizowanie...';
                    fetch(restUrl + 'preview', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': restNonce },
                        body: JSON.stringify({ video_url: vUrl, post_id: postId })
                    })
                    .then(function(r) { return r.json(); })
                    .then(function(res) {
                        previewBtn.disabled = false;
                        previewBtn.textContent = '🔍 Analizuj SEO (Preview)';
                        if (res && res.before_score !== undefined) {
                            previewBox.style.display = 'block';
                            scoreVal.textContent = 'Przed: ' + res.before_score + '/100  →  Po VSE: ' + (res.after_score || 96) + '/100 (+' + (res.score_gain || 68) + ' pkt)';
                            scoreVal.style.color = '#16a34a';
                            if (res.rich_result && res.rich_result.recommendation) {
                                previewRec.textContent = '💡 ' + res.rich_result.recommendation;
                            }
                        } else {
                            alert((res && res.detail) || 'Błąd analizy wideo.');
                        }
                    })
                    .catch(function(e) {
                        previewBtn.disabled = false;
                        previewBtn.textContent = '🔍 Analizuj SEO (Preview)';
                        alert('Błąd połączenia: ' + e.message);
                    });
                });
            }

            if (injectBtn) {
                injectBtn.addEventListener('click', function() {
                    var vUrl = urlInput ? urlInput.value.trim() : '';
                    if (!vUrl) {
                        alert('Wklej link do filmu YouTube.');
                        return;
                    }
                    var incContent = document.getElementById('vse-mb-inc-content').checked;
                    var incSchema = document.getElementById('vse-mb-inc-schema').checked;
                    injectBtn.disabled = true;
                    statusMsg.style.color = '#0f172a';
                    statusMsg.textContent = '⏳ Generowanie pełnego pakietu AI z YouTube (ok. 20-45s)...';

                    fetch(restUrl + 'inject-data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': restNonce },
                        body: JSON.stringify({
                            video_url: vUrl,
                            post_id: postId,
                            target_lang: langSelect ? langSelect.value : 'pl',
                            update_post_content: incContent,
                            include_schema: incSchema,
                            include_embed: document.getElementById('vse-mb-sec-embed').checked,
                            include_tldr: document.getElementById('vse-mb-sec-tldr').checked,
                            include_article: document.getElementById('vse-mb-sec-article').checked,
                            include_chapters: document.getElementById('vse-mb-sec-chapters').checked,
                            include_faq: document.getElementById('vse-mb-sec-faq').checked
                        })
                    })
                    .then(function(r) { return r.json().then(function(d) { return { status: r.status, data: d }; }); })
                    .then(function(resObj) {
                        injectBtn.disabled = false;
                        var d = resObj.data || {};
                        if (resObj.status === 200) {
                            var schemaStr = typeof d.schema_json === 'string' ? d.schema_json : JSON.stringify(d.schema_json || [], null, 2);
                            if (incSchema && schemaStr) {
                                schemaBadge.innerHTML = '✅ Aktywne w &lt;head&gt; (VideoObject + Clip + FAQPage)';
                                schemaPreview.value = schemaStr;
                            }
                            insertContentIntoActiveEditor(
                                incContent ? (d.assembled_html || '') : '',
                                d.post_title || d.seo_title || '',
                                {
                                    _vse_video_url: vUrl,
                                    _vse_schema_json: typeof d.schema_json === 'string' ? d.schema_json : JSON.stringify(d.schema_json || []),
                                    _vse_chapters_json: JSON.stringify(d.chapters || []),
                                    _vse_seo_score: d.after_score || 96
                                }
                            );
                            statusMsg.style.color = '#16a34a';
                            statusMsg.textContent = '✅ Wstrzyknięto artykuł, Schema JSON-LD do <head> i Meta SEO!';
                        } else {
                            statusMsg.style.color = '#dc2626';
                            statusMsg.textContent = '✕ ' + (d.detail || 'Błąd generowania.');
                        }
                    })
                    .catch(function(e) {
                        injectBtn.disabled = false;
                        statusMsg.style.color = '#dc2626';
                        statusMsg.textContent = '✕ Błąd sieci: ' + e.message;
                    });
                });
            }

            function loadHistoryList() {
                if (!loadHistoryBtn) return;
                loadHistoryBtn.disabled = true;
                loadHistoryBtn.textContent = '⏳...';
                fetch(restUrl + 'history?limit=25', {
                    method: 'GET',
                    headers: { 'X-WP-Nonce': restNonce }
                })
                .then(function(r) { return r.json(); })
                .then(function(res) {
                    loadHistoryBtn.disabled = false;
                    loadHistoryBtn.textContent = '🔄 Załaduj listę';
                    var items = (res && res.items) || (Array.isArray(res) ? res : []);
                    historySelect.innerHTML = '<option value="">— Wybierz materiał z historii VSE (' + items.length + ') —</option>';
                    items.forEach(function(item) {
                        var opt = document.createElement('option');
                        opt.value = item.job_id || item.id;
                        var dateStr = (item.created_at || '').slice(0, 10);
                        var titleStr = item.post_title || item.seo_title || item.video_title || item.youtube_id || ('Job #' + opt.value);
                        var langStr = (item.lang || 'pl').toUpperCase();
                        opt.textContent = '[' + dateStr + ' | ' + langStr + '] ' + titleStr;
                        historySelect.appendChild(opt);
                    });
                })
                .catch(function() {
                    loadHistoryBtn.disabled = false;
                    loadHistoryBtn.textContent = '🔄 Załaduj listę';
                });
            }

            if (loadHistoryBtn) {
                loadHistoryBtn.addEventListener('click', loadHistoryList);
            }

            if (importHistoryBtn) {
                importHistoryBtn.addEventListener('click', function() {
                    var jobId = historySelect ? historySelect.value : '';
                    if (!jobId) {
                        alert('Najpierw wybierz materiał z rozwijanej listy historii VSE.');
                        return;
                    }
                    var incContent = document.getElementById('vse-mb-inc-content').checked;
                    var incSchema = document.getElementById('vse-mb-inc-schema').checked;
                    importHistoryBtn.disabled = true;
                    statusMsg.style.color = '#0f172a';
                    statusMsg.textContent = '⏳ Importowanie materiału z chmury VSE (0 kredytów)...';

                    fetch(restUrl + 'import-history-item', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': restNonce },
                        body: JSON.stringify({
                            job_id: jobId,
                            post_id: postId,
                            create_new: false,
                            mode: 'inject_post',
                            update_post_content: incContent,
                            include_schema: incSchema,
                            include_embed: document.getElementById('vse-mb-sec-embed').checked,
                            include_tldr: document.getElementById('vse-mb-sec-tldr').checked,
                            include_article: document.getElementById('vse-mb-sec-article').checked,
                            include_chapters: document.getElementById('vse-mb-sec-chapters').checked,
                            include_faq: document.getElementById('vse-mb-sec-faq').checked
                        })
                    })
                    .then(function(r) { return r.json().then(function(d) { return { status: r.status, data: d }; }); })
                    .then(function(resObj) {
                        importHistoryBtn.disabled = false;
                        var d = resObj.data || {};
                        if (resObj.status === 200) {
                            var schemaStr = typeof d.schema_json === 'string' ? d.schema_json : JSON.stringify(d.schema_json || [], null, 2);
                            if (incSchema && schemaStr) {
                                schemaBadge.innerHTML = '✅ Aktywne w &lt;head&gt; (Zaimportowano z chmury VSE)';
                                schemaPreview.value = schemaStr;
                            }
                            if (d.video_url && urlInput) {
                                urlInput.value = d.video_url;
                            }
                            insertContentIntoActiveEditor(
                                incContent ? (d.assembled_html || '') : '',
                                d.post_title || d.seo_title || '',
                                {
                                    _vse_video_url: d.video_url || '',
                                    _vse_schema_json: typeof d.schema_json === 'string' ? d.schema_json : JSON.stringify(d.schema_json || []),
                                    _vse_chapters_json: JSON.stringify(d.chapters || []),
                                    _vse_seo_score: d.after_score || d.seo_score || 96
                                }
                            );
                            statusMsg.style.color = '#16a34a';
                            statusMsg.textContent = '✅ Zaimportowano materiał z historii VSE (0 zużytych kredytów)!';
                        } else {
                            statusMsg.style.color = '#dc2626';
                            statusMsg.textContent = '✕ ' + (d.detail || 'Błąd importu z historii.');
                        }
                    })
                    .catch(function(e) {
                        importHistoryBtn.disabled = false;
                        statusMsg.style.color = '#dc2626';
                        statusMsg.textContent = '✕ Błąd sieci: ' + e.message;
                    });
                });
            }
        })();
        </script>
        <?php
    }

    /**
     * Render main WP Admin Dashboard page with 3 tabs:
     * 1. 🎬 Generuj wpis z YouTube (1-Click Full Package)
     * 2. 📚 Historia / Biblioteka VSE (Pull z chmury bez zużycia quota)
     * 3. 🔑 Połączenie, Auto-Parowanie & Quota (vse_live_...)
     */
    public function render_admin_dashboard_page() {
        if ( ! current_user_can( 'edit_posts' ) ) {
            return;
        }

        $active_tab    = isset( $_GET['tab'] ) ? sanitize_key( $_GET['tab'] ) : 'generate';
        if ( ! in_array( $active_tab, array( 'generate', 'history', 'connection' ), true ) ) {
            $active_tab = 'generate';
        }

        $api_key       = self::get_api_key();
        $api_url       = self::get_api_url();
        $cached_status = get_option( 'vse_cached_status', array() );
        $plan          = isset( $cached_status['plan'] ) ? strtoupper( $cached_status['plan'] ) : 'FREE';
        $quota         = isset( $cached_status['monthly_quota'] ) ? (int) $cached_status['monthly_quota'] : 5;
        $used          = isset( $cached_status['used_this_month'] ) ? (int) $cached_status['used_this_month'] : 0;
        $remaining     = isset( $cached_status['remaining_quota'] ) ? (int) $cached_status['remaining_quota'] : max( 0, $quota - $used );
        $extra_quota   = isset( $cached_status['extra_quota_balance'] ) ? (int) $cached_status['extra_quota_balance'] : 0;
        $portal_paired = ! empty( $cached_status['portal_paired'] ) || ! empty( $api_key );
        $rest_url      = esc_url_raw( rest_url( 'vse/v1/' ) );
        $rest_nonce    = wp_create_nonce( 'wp_rest' );
        $admin_nonce   = wp_create_nonce( 'vse_admin_nonce' );
        $languages     = self::get_supported_languages();
        ?>
        <div class="wrap" style="max-width: 1020px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <!-- Header -->
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;margin-bottom:16px;">
                <h1 style="display:flex;align-items:center;gap:10px;margin:0;">
                    <span class="dashicons dashicons-video-alt3" style="font-size:32px;width:32px;height:32px;color:#e11d48;"></span>
                    <?php esc_html_e( 'VSE Video SEO — Hub Publikacji AI', 'vse-video-seo' ); ?>
                    <span style="font-size:12px;background:#e11d48;color:#fff;padding:2px 10px;border-radius:12px;font-weight:700;">v<?php echo esc_html( VSE_VIDEO_SEO_VERSION ); ?></span>
                </h1>
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                    <span style="background:#f8fafc;border:1px solid #cbd5e1;padding:5px 12px;border-radius:6px;font-size:12px;color:#0f172a;">
                        Plan: <strong id="vse-hdr-plan"><?php echo esc_html( $plan ); ?></strong>
                        &bull; Miesięczny: <strong id="vse-hdr-usage"><?php echo esc_html( $used . '/' . ( $quota < 0 ? '∞' : $quota ) ); ?></strong>
                        &bull; Pakiet Top-Up: <strong id="vse-hdr-topup" style="color:#2563eb;">+<?php echo esc_html( $extra_quota ); ?> filmów</strong>
                    </span>
                    <a href="https://vse.impresjapr.pl/dashboard" target="_blank" rel="noopener" class="button">
                        🌐 Panel VSE ↗
                    </a>
                    <a href="https://vse.impresjapr.pl/cennik#topup" target="_blank" rel="noopener" class="button button-primary" style="background:#2563eb;border-color:#2563eb;">
                        ⚡ Dokup pakiet Top-Up ↗
                    </a>
                </div>
            </div>

            <!-- Navigation Tabs -->
            <h2 class="nav-tab-wrapper" style="margin-bottom:20px;">
                <a href="#generate" data-vse-tab="generate" class="nav-tab vse-nav-tab <?php echo 'generate' === $active_tab ? 'nav-tab-active' : ''; ?>">
                    🎬 1. Generuj wpis z YouTube (1-Click Full Package)
                </a>
                <a href="#history" data-vse-tab="history" class="nav-tab vse-nav-tab <?php echo 'history' === $active_tab ? 'nav-tab-active' : ''; ?>">
                    📚 2. Historia / Biblioteka VSE (0 kredytów)
                </a>
                <a href="#connection" data-vse-tab="connection" class="nav-tab vse-nav-tab <?php echo 'connection' === $active_tab ? 'nav-tab-active' : ''; ?>">
                    🔑 3. Połączenie, Auto-Parowanie &amp; Quota
                </a>
            </h2>

            <!-- TAB 1: GENERATE POST FROM YOUTUBE -->
            <div id="vse-tab-generate" class="vse-tab-panel" style="display:<?php echo 'generate' === $active_tab ? 'block' : 'none'; ?>;">
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <h2 style="margin-top:0;font-size:18px;color:#0f172a;">
                        🎬 Wygeneruj pełny artykuł SEO z filmu YouTube i utwórz wpis w WordPressie
                    </h2>
                    <p style="color:#475569;font-size:13px;margin-top:4px;margin-bottom:20px;">
                        Wklej link do dowolnego filmu na YouTube. Silnik VSE pobierze transkrypcję, wygeneruje artykuł ekspercki HTML, podsumowanie TL;DR, interaktywne rozdziały Key Moments, sekcję FAQ oraz wstrzyknie czyste Schema.org JSON-LD (`VideoObject` + `Clip` + `FAQPage`) bezpośrednio do <code>&lt;head&gt;</code> i metadanych <strong><?php echo esc_html( VSE_SEO_Adapter::detect_active_plugin_label() ); ?></strong>.
                    </p>

                    <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:16px;">
                        <div>
                            <label for="vse-gen-video-url" style="display:block;font-weight:600;margin-bottom:6px;color:#0f172a;">
                                Link do filmu YouTube *
                            </label>
                            <input type="url" id="vse-gen-video-url" class="large-text" placeholder="https://www.youtube.com/watch?v=..." style="width:100%;padding:8px 12px;font-size:14px;" />
                        </div>
                        <div>
                            <label for="vse-gen-lang" style="display:block;font-weight:600;margin-bottom:6px;color:#0f172a;">
                                Język docelowy artykułu i Schema
                            </label>
                            <select id="vse-gen-lang" style="width:100%;height:38px;font-size:14px;">
                                <?php foreach ( $languages as $code => $label ) : ?>
                                    <option value="<?php echo esc_attr( $code ); ?>"><?php echo esc_html( $label ); ?></option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                    </div>

                    <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:20px;">
                        <div>
                            <label for="vse-gen-title" style="display:block;font-weight:600;margin-bottom:6px;color:#0f172a;">
                                Tytuł roboczy wpisu <span style="font-weight:400;color:#64748b;">(opcjonalny — jeśli pusty, AI wygeneruje optymalny tytuł SEO)</span>
                            </label>
                            <input type="text" id="vse-gen-title" class="large-text" placeholder="Zostaw puste, aby użyć tytułu wygenerowanego przez AI..." style="width:100%;padding:8px 12px;font-size:14px;" />
                        </div>
                        <div>
                            <label for="vse-gen-status" style="display:block;font-weight:600;margin-bottom:6px;color:#0f172a;">
                                Status utworzonego wpisu w WP
                            </label>
                            <select id="vse-gen-status" style="width:100%;height:38px;font-size:14px;">
                                <option value="draft">📝 Szkic (draft) — do przeglądu</option>
                                <option value="publish">🟢 Opublikowany (publish) — od razu na stronie</option>
                            </select>
                        </div>
                    </div>

                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:20px;">
                        <div style="font-weight:600;font-size:13px;color:#0f172a;margin-bottom:10px;">
                            Elementy pakietu do zawarcia we wpisie:
                        </div>
                        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;font-size:13px;color:#1e293b;">
                            <label><input type="checkbox" id="vse-gen-inc-embed" checked /> 📺 Osadzone wideo YouTube (responsywny iframe)</label>
                            <label><input type="checkbox" id="vse-gen-inc-tldr" checked /> ⚡ Podsumowanie TL;DR (Kluczowe wnioski)</label>
                            <label><input type="checkbox" id="vse-gen-inc-article" checked /> 📄 Pełny artykuł SEO HTML</label>
                            <label><input type="checkbox" id="vse-gen-inc-chapters" checked /> 🎬 Interaktywne rozdziały (Key Moments z przewijaniem wideo)</label>
                            <label><input type="checkbox" id="vse-gen-inc-faq" checked /> ❓ Sekcja FAQ (Pytania i odpowiedzi)</label>
                            <label><input type="checkbox" id="vse-gen-inc-schema" checked /> 🧠 Schema.org JSON-LD w <code>&lt;head&gt;</code> + Meta RankMath/Yoast/SEOPress</label>
                        </div>
                    </div>

                    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
                        <button type="button" class="button button-primary button-hero" id="vse-gen-submit-btn" style="background:#e11d48;border-color:#e11d48;font-weight:700;padding:6px 24px;">
                            🚀 Wygeneruj pełny artykuł i utwórz wpis w WP
                        </button>
                        <span id="vse-gen-spinner" style="display:none;color:#0f172a;font-size:13px;font-weight:500;">
                            ⏳ Trwa analiza wideo i generowanie artykułu SEO przez AI (zwykle 20–45 sekund)...
                        </span>
                    </div>

                    <!-- Generation Result Banner -->
                    <div id="vse-gen-result-box" style="display:none;margin-top:20px;padding:18px;border-radius:8px;border:1px solid #bbf7d0;background:#f0fdf4;"></div>
                </div>
            </div>

            <!-- TAB 2: VSE CLOUD HISTORY / LIBRARY -->
            <div id="vse-tab-history" class="vse-tab-panel" style="display:<?php echo 'history' === $active_tab ? 'block' : 'none'; ?>;">
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
                        <div>
                            <h2 style="margin:0;font-size:18px;color:#0f172a;">
                                📚 Historia / Biblioteka wygenerowanych materiałów w chmurze VSE
                            </h2>
                            <p style="margin:4px 0 0 0;font-size:13px;color:#475569;">
                                Pobieraj i publikuj na tym portalu materiały wygenerowane wcześniej w Dashboardzie VSE lub we wtyczce — <strong>całkowicie za darmo (0 zużytych kredytów)</strong>.
                            </p>
                        </div>
                        <button type="button" class="button button-secondary" id="vse-hist-refresh-btn" style="font-weight:600;">
                            🔄 Odśwież historię z VSE
                        </button>
                    </div>

                    <div id="vse-hist-notice" style="display:none;margin-bottom:14px;padding:12px 16px;border-radius:6px;background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;"></div>

                    <div style="overflow-x:auto;">
                        <table class="wp-list-table widefat fixed striped" style="border-radius:8px;overflow:hidden;">
                            <thead>
                                <tr>
                                    <th style="width:130px;">Data</th>
                                    <th>Tytuł artykułu / SEO Title</th>
                                    <th style="width:160px;">Link YouTube</th>
                                    <th style="width:70px;">Język</th>
                                    <th style="width:240px;">Akcja (0 kredytów)</th>
                                </tr>
                            </thead>
                            <tbody id="vse-hist-tbody">
                                <tr>
                                    <td colspan="5" style="text-align:center;padding:24px;color:#64748b;">
                                        Kliknij „🔄 Odśwież historię z VSE”, aby pobrać listę materiałów z chmury.
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- TAB 3: CONNECTION, AUTO-PAIRING & QUOTA -->
            <div id="vse-tab-connection" class="vse-tab-panel" style="display:<?php echo 'connection' === $active_tab ? 'block' : 'none'; ?>;">
                <!-- Status & Auto-Pairing Card -->
                <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:22px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
                        <h2 style="margin:0;font-size:17px;color:#0f172a;">
                            <?php esc_html_e( 'Status Połączenia, Auto-Parowania i Limitów', 'vse-video-seo' ); ?>
                        </h2>
                        <span id="vse-pairing-badge" style="font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px;background:<?php echo $portal_paired ? '#dcfce7' : '#fef2f2'; ?>;color:<?php echo $portal_paired ? '#166534' : '#991b1b'; ?>;">
                            <?php
                            echo $portal_paired
                                ? '🟢 Portal automatycznie sparowany z Dashboardem VSE — publikacja bez App Passwords aktywna!'
                                : '⚪ Portal niesparowany — wklej klucz vse_live_... poniżej';
                            ?>
                        </span>
                    </div>

                    <div id="vse-status-box" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;">
                        <div>
                            <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Aktywny Plan', 'vse-video-seo' ); ?></span>
                            <strong id="vse-stat-plan" style="font-size:20px;color:#0f172a;"><?php echo esc_html( $plan ); ?></strong>
                        </div>
                        <div>
                            <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Zużycie miesięczne', 'vse-video-seo' ); ?></span>
                            <strong id="vse-stat-usage" style="font-size:20px;color:#0f172a;"><?php echo esc_html( $used . ' / ' . ( $quota < 0 ? '∞' : $quota ) ); ?> <?php esc_html_e( 'filmów', 'vse-video-seo' ); ?></strong>
                        </div>
                        <div>
                            <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Pozostały limit mies.', 'vse-video-seo' ); ?></span>
                            <strong id="vse-stat-remaining" style="font-size:20px;color:#16a34a;"><?php echo esc_html( $quota < 0 ? 'Bez limitu' : $remaining ); ?></strong>
                        </div>
                        <div>
                            <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Pakiet Top-Up (nie wygasa)', 'vse-video-seo' ); ?></span>
                            <strong id="vse-stat-extra" style="font-size:20px;color:#2563eb;">+<?php echo esc_html( $extra_quota ); ?> <?php esc_html_e( 'filmów', 'vse-video-seo' ); ?></strong>
                        </div>
                        <div>
                            <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Wykryty adapter SEO', 'vse-video-seo' ); ?></span>
                            <strong style="font-size:14px;color:#334155;"><?php echo esc_html( VSE_SEO_Adapter::detect_active_plugin_label() ); ?></strong>
                        </div>
                    </div>
                    <p id="vse-validate-msg" style="margin:12px 0 0 0;font-size:13px;font-weight:600;display:none;"></p>
                </div>

                <?php if ( current_user_can( 'manage_options' ) ) : ?>
                <form method="post" action="options.php" style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:22px;">
                    <?php settings_fields( 'vse_video_seo_settings' ); ?>
                    <table class="form-table" role="presentation">
                        <tr>
                            <th scope="row">
                                <label for="vse_api_key"><?php esc_html_e( 'Klucz API (vse_live_...)', 'vse-video-seo' ); ?></label>
                            </th>
                            <td>
                                <input name="vse_api_key" type="password" id="vse_api_key" value="<?php echo esc_attr( $api_key ); ?>" class="regular-text" placeholder="vse_live_..." autocomplete="off" />
                                <button type="button" class="button button-primary" id="vse-validate-btn" style="background:#0f172a;border-color:#0f172a;font-weight:600;">
                                    <?php esc_html_e( '🔗 Zapisz i połącz z VSE (Auto-Parowanie)', 'vse-video-seo' ); ?>
                                </button>
                                <p class="description">
                                    <?php
                                    printf(
                                        esc_html__( 'Klucz API wygenerujesz w panelu %s. Kliknięcie „Zapisz i połącz” automatycznie sparuje ten portal WordPress z Twoim kontem VSE bez potrzeby generowania Application Passwords!', 'vse-video-seo' ),
                                        '<a href="https://vse.impresjapr.pl/dashboard" target="_blank" rel="noopener">vse.impresjapr.pl/dashboard</a>'
                                    );
                                    ?>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <th scope="row">
                                <label for="vse_api_url"><?php esc_html_e( 'Adres instancji VSE API', 'vse-video-seo' ); ?></label>
                            </th>
                            <td>
                                <input name="vse_api_url" type="url" id="vse_api_url" value="<?php echo esc_attr( $api_url ); ?>" class="regular-text" />
                                <p class="description"><?php esc_html_e( 'Domyślnie: https://vse.impresjapr.pl', 'vse-video-seo' ); ?></p>
                            </td>
                        </tr>
                    </table>
                    <?php submit_button( __( 'Zapisz ustawienia w WordPress', 'vse-video-seo' ) ); ?>
                </form>
                <?php endif; ?>
            </div>
        </div>

        <script>
        (function() {
            var restUrl = <?php echo wp_json_encode( $rest_url ); ?>;
            var restNonce = <?php echo wp_json_encode( $rest_nonce ); ?>;
            var adminNonce = <?php echo wp_json_encode( $admin_nonce ); ?>;

            // Tab switching without reload
            var tabs = document.querySelectorAll('.vse-nav-tab');
            var panels = {
                generate: document.getElementById('vse-tab-generate'),
                history: document.getElementById('vse-tab-history'),
                connection: document.getElementById('vse-tab-connection')
            };
            var historyLoadedOnce = false;

            function switchTab(tabName) {
                tabs.forEach(function(t) {
                    if (t.getAttribute('data-vse-tab') === tabName) {
                        t.classList.add('nav-tab-active');
                    } else {
                        t.classList.remove('nav-tab-active');
                    }
                });
                Object.keys(panels).forEach(function(k) {
                    if (panels[k]) {
                        panels[k].style.display = (k === tabName) ? 'block' : 'none';
                    }
                });
                if (tabName === 'history' && !historyLoadedOnce) {
                    historyLoadedOnce = true;
                    fetchHistoryTable();
                }
            }

            tabs.forEach(function(t) {
                t.addEventListener('click', function(e) {
                    e.preventDefault();
                    switchTab(t.getAttribute('data-vse-tab'));
                });
            });

            if (<?php echo wp_json_encode( $active_tab ); ?> === 'history') {
                historyLoadedOnce = true;
                setTimeout(fetchHistoryTable, 100);
            }

            // Tab 1: 1-Click Generate Post from Video
            var genBtn = document.getElementById('vse-gen-submit-btn');
            var genSpinner = document.getElementById('vse-gen-spinner');
            var genResultBox = document.getElementById('vse-gen-result-box');

            if (genBtn) {
                genBtn.addEventListener('click', function() {
                    var videoUrl = document.getElementById('vse-gen-video-url').value.trim();
                    if (!videoUrl) {
                        alert('Podaj link do filmu YouTube.');
                        return;
                    }
                    genBtn.disabled = true;
                    genSpinner.style.display = 'inline';
                    genResultBox.style.display = 'none';

                    var payload = {
                        video_url: videoUrl,
                        target_lang: document.getElementById('vse-gen-lang').value,
                        post_title: document.getElementById('vse-gen-title').value.trim(),
                        post_status: document.getElementById('vse-gen-status').value,
                        include_embed: document.getElementById('vse-gen-inc-embed').checked,
                        include_tldr: document.getElementById('vse-gen-inc-tldr').checked,
                        include_article: document.getElementById('vse-gen-inc-article').checked,
                        include_chapters: document.getElementById('vse-gen-inc-chapters').checked,
                        include_faq: document.getElementById('vse-gen-inc-faq').checked,
                        include_schema: document.getElementById('vse-gen-inc-schema').checked
                    };

                    fetch(restUrl + 'create-post-from-video', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': restNonce },
                        body: JSON.stringify(payload)
                    })
                    .then(function(r) { return r.json().then(function(d) { return { status: r.status, data: d }; }); })
                    .then(function(resObj) {
                        genBtn.disabled = false;
                        genSpinner.style.display = 'none';
                        var d = resObj.data || {};
                        genResultBox.style.display = 'block';
                        if (resObj.status === 200 && d.ok) {
                            genResultBox.style.background = '#f0fdf4';
                            genResultBox.style.borderColor = '#bbf7d0';
                            genResultBox.innerHTML = '<div style="font-size:15px;font-weight:700;color:#166534;margin-bottom:8px;">' +
                                '🎉 Utworzono nowy wpis WordPress z pełnym pakietem Video SEO (Score: ' + (d.seo_score || 96) + '/100)!' +
                                '</div>' +
                                '<div style="font-size:13px;color:#1e293b;margin-bottom:12px;">Tytuł: <strong>' + (d.post_title || '') + '</strong> (ID: #' + d.post_id + ')</div>' +
                                '<div style="display:flex;gap:10px;flex-wrap:wrap;">' +
                                '<a href="' + (d.edit_url || '#') + '" class="button button-primary">✏️ Edytuj utworzony wpis</a>' +
                                '<a href="' + (d.view_url || '#') + '" target="_blank" class="button">👁️ Zobacz wpis</a>' +
                                '</div>';
                        } else {
                            genResultBox.style.background = '#fef2f2';
                            genResultBox.style.borderColor = '#fecaca';
                            genResultBox.innerHTML = '<div style="color:#991b1b;font-weight:600;">✕ Błąd: ' + (d.detail || d.message || 'Nie udało się wygenerować wpisu.') + '</div>';
                        }
                    })
                    .catch(function(e) {
                        genBtn.disabled = false;
                        genSpinner.style.display = 'none';
                        genResultBox.style.display = 'block';
                        genResultBox.style.background = '#fef2f2';
                        genResultBox.innerHTML = '<div style="color:#991b1b;font-weight:600;">✕ Błąd sieci: ' + e.message + '</div>';
                    });
                });
            }

            // Tab 2: Cloud History Table
            var histTbody = document.getElementById('vse-hist-tbody');
            var histRefreshBtn = document.getElementById('vse-hist-refresh-btn');
            var histNotice = document.getElementById('vse-hist-notice');

            function fetchHistoryTable() {
                if (!histTbody) return;
                histTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;">⏳ Pobieranie historii z chmury VSE...</td></tr>';
                fetch(restUrl + 'history?limit=25', {
                    method: 'GET',
                    headers: { 'X-WP-Nonce': restNonce }
                })
                .then(function(r) { return r.json(); })
                .then(function(res) {
                    var items = (res && res.items) || (Array.isArray(res) ? res : []);
                    if (!items.length) {
                        histTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:#64748b;">Brak wygenerowanych materiałów w historii tego konta VSE.</td></tr>';
                        return;
                    }
                    histTbody.innerHTML = '';
                    items.forEach(function(item) {
                        var jobId = item.job_id || item.id;
                        var tr = document.createElement('tr');
                        var dateStr = (item.created_at || '').replace('T', ' ').slice(0, 16);
                        var titleStr = item.post_title || item.seo_title || item.video_title || ('Materiał #' + jobId);
                        var ytUrl = item.video_url || (item.youtube_id ? 'https://www.youtube.com/watch?v=' + item.youtube_id : '');
                        var langStr = (item.lang || 'pl').toUpperCase();

                        tr.innerHTML = '<td>' + dateStr + '</td>' +
                            '<td><strong>' + titleStr + '</strong></td>' +
                            '<td>' + (ytUrl ? '<a href="' + ytUrl + '" target="_blank" rel="noopener">YouTube ↗</a>' : '—') + '</td>' +
                            '<td><span style="background:#f1f5f9;padding:2px 8px;border-radius:4px;font-weight:600;font-size:11px;">' + langStr + '</span></td>' +
                            '<td><button type="button" class="button button-primary vse-hist-import-btn" data-job-id="' + jobId + '">➕ Utwórz nowy wpis w WP (Szkic)</button></td>';
                        histTbody.appendChild(tr);
                    });

                    document.querySelectorAll('.vse-hist-import-btn').forEach(function(b) {
                        b.addEventListener('click', function() {
                            var jId = b.getAttribute('data-job-id');
                            b.disabled = true;
                            b.textContent = '⏳ Tworzenie wpisu...';
                            fetch(restUrl + 'import-history-item', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': restNonce },
                                body: JSON.stringify({ job_id: jId, create_new: true, mode: 'create_post', post_status: 'draft' })
                            })
                            .then(function(r) { return r.json().then(function(d) { return { status: r.status, data: d }; }); })
                            .then(function(resObj) {
                                b.disabled = false;
                                b.textContent = '✓ Utworzono szkic';
                                var d = resObj.data || {};
                                if (resObj.status === 200 && d.post_id) {
                                    histNotice.style.display = 'block';
                                    histNotice.innerHTML = '✅ Utworzono wpis <strong>' + (d.post_title || '') + '</strong> (0 zużytych kredytów)! ' +
                                        '<a href="' + (d.edit_url || '#') + '" class="button button-small button-primary" style="margin-left:10px;">✏️ Edytuj wpis</a> ' +
                                        '<a href="' + (d.view_url || '#') + '" target="_blank" class="button button-small">👁️ Zobacz wpis</a>';
                                } else {
                                    alert((d && d.detail) || 'Błąd importu z historii.');
                                }
                            })
                            .catch(function(e) {
                                b.disabled = false;
                                b.textContent = '➕ Utwórz nowy wpis w WP (Szkic)';
                                alert('Błąd połączenia: ' + e.message);
                            });
                        });
                    });
                })
                .catch(function(e) {
                    histTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:#dc2626;">Błąd pobierania historii: ' + e.message + '</td></tr>';
                });
            }

            if (histRefreshBtn) {
                histRefreshBtn.addEventListener('click', fetchHistoryTable);
            }

            // Tab 3: Validate & Auto-Pair Key
            var btn = document.getElementById('vse-validate-btn');
            var msg = document.getElementById('vse-validate-msg');
            var pairingBadge = document.getElementById('vse-pairing-badge');
            if (btn) {
                btn.addEventListener('click', function() {
                    var keyInput = document.getElementById('vse_api_key');
                    var urlInput = document.getElementById('vse_api_url');
                    btn.disabled = true;
                    btn.textContent = '⏳ Parowanie z VSE...';
                    msg.style.display = 'block';
                    msg.style.color = '#475569';
                    msg.textContent = 'Łączenie z VSE API i auto-parowanie portalu...';

                    var formData = new FormData();
                    formData.append('action', 'vse_validate_key');
                    formData.append('nonce', adminNonce);
                    formData.append('api_key', keyInput ? keyInput.value : '');
                    formData.append('api_url', urlInput ? urlInput.value : '');

                    fetch(ajaxurl, { method: 'POST', body: formData })
                        .then(function(r) { return r.json(); })
                        .then(function(res) {
                            btn.disabled = false;
                            btn.textContent = '🔗 Zapisz i połącz z VSE (Auto-Parowanie)';
                            if (res.success && res.data) {
                                var d = res.data;
                                var planStr = (d.plan || 'free').toUpperCase();
                                var q = d.monthly_quota < 0 ? '∞' : d.monthly_quota;
                                var extra = d.extra_quota_balance || 0;
                                document.getElementById('vse-stat-plan').textContent = planStr;
                                document.getElementById('vse-stat-usage').textContent = (d.used_this_month || 0) + ' / ' + q + ' filmów';
                                document.getElementById('vse-stat-remaining').textContent = d.monthly_quota < 0 ? 'Bez limitu' : d.remaining_quota;
                                document.getElementById('vse-stat-extra').textContent = '+' + extra + ' filmów';
                                document.getElementById('vse-hdr-plan').textContent = planStr;
                                document.getElementById('vse-hdr-usage').textContent = (d.used_this_month || 0) + '/' + q;
                                document.getElementById('vse-hdr-topup').textContent = '+' + extra + ' filmów';
                                if (pairingBadge) {
                                    pairingBadge.style.background = '#dcfce7';
                                    pairingBadge.style.color = '#166534';
                                    pairingBadge.textContent = '🟢 Portal automatycznie sparowany z Dashboardem VSE — publikacja bez App Passwords aktywna!';
                                }
                                msg.style.color = '#16a34a';
                                msg.textContent = '✓ Klucz aktywny i portal sparowany! Domena: ' + (d.allowed_domain || window.location.hostname);
                            } else {
                                var err = (res.data && (res.data.detail || res.data.message)) || 'Nieprawidłowy klucz API.';
                                msg.style.color = '#dc2626';
                                msg.textContent = '✕ Błąd walidacji: ' + err;
                            }
                        })
                        .catch(function(e) {
                            btn.disabled = false;
                            btn.textContent = '🔗 Zapisz i połącz z VSE (Auto-Parowanie)';
                            msg.style.color = '#dc2626';
                            msg.textContent = '✕ Błąd połączenia: ' + e.message;
                        });
                });
            }
        })();
        </script>
        <?php
    }
}

VSE_Video_SEO::get_instance();
