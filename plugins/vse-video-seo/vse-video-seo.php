<?php
/**
 * Plugin Name:       VSE Video SEO — AI Schema & Chapters
 * Plugin URI:        https://vse.impresjapr.pl
 * Description:       Automatyczna optymalizacja Video SEO z AI: wstrzykiwanie czystego VideoObject + Clip (Key Moments) + FAQPage JSON-LD Schema do <head>, synchronizacja z RankMath / Yoast / SEOPress oraz interaktywne rozdziały YouTube.
 * Version:           2.0.0
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

define( 'VSE_VIDEO_SEO_VERSION', '2.0.0' );
define( 'VSE_VIDEO_SEO_DIR', plugin_dir_path( __FILE__ ) );
define( 'VSE_VIDEO_SEO_URL', plugin_dir_url( __FILE__ ) );
define( 'VSE_DEFAULT_API_URL', 'https://vse.impresjapr.pl' );

require_once VSE_VIDEO_SEO_DIR . 'includes/class-vse-head-injector.php';
require_once VSE_VIDEO_SEO_DIR . 'includes/class-vse-seo-adapter.php';
require_once VSE_VIDEO_SEO_DIR . 'includes/class-vse-gutenberg.php';

/**
 * Main plugin class for VSE Video SEO.
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
        add_action( 'admin_menu', array( $this, 'register_settings_page' ) );
        add_action( 'admin_init', array( $this, 'register_settings' ) );
        add_action( 'rest_api_init', array( $this, 'register_rest_routes' ) );
        add_action( 'wp_enqueue_scripts', array( $this, 'enqueue_frontend_assets' ) );

        // WP AJAX handlers for admin settings & editor fallback
        add_action( 'wp_ajax_vse_validate_key', array( $this, 'ajax_validate_key' ) );
        add_action( 'wp_ajax_vse_preview', array( $this, 'ajax_preview' ) );
        add_action( 'wp_ajax_vse_inject_data', array( $this, 'ajax_inject_data' ) );

        // Initialize sub-components
        VSE_Head_Injector::init();
        VSE_Gutenberg::init();
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
     * Register Settings -> VSE Video SEO menu item.
     */
    public function register_settings_page() {
        add_options_page(
            __( 'VSE Video SEO — Ustawienia', 'vse-video-seo' ),
            __( 'VSE Video SEO', 'vse-video-seo' ),
            'manage_options',
            'vse-video-seo',
            array( $this, 'render_settings_page' )
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
     * Register WP REST API proxy endpoints for Gutenberg Sidebar.
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
     */
    public function rest_validate_key( WP_REST_Request $request ) {
        $api_key = sanitize_text_field( $request->get_param( 'api_key' ) ?: self::get_api_key() );
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'valid'   => false,
                'message' => __( 'Brak klucza API VSE. Wklej klucz w Ustawienia → VSE Video SEO.', 'vse-video-seo' ),
            ), 400 );
        }

        $res = self::call_backend( '/v1/plugin/validate', array(
            'api_key' => $api_key,
            'domain'  => self::get_site_domain(),
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
                    ? (int) ( $res['data']['after_score'] ?? 94 )
                    : (int) $res['data']['before_score'];
                update_post_meta( $post_id, '_vse_seo_score', $score_to_save );
            }
        }

        return new WP_REST_Response( $res['data'], $res['status_code'] );
    }

    /**
     * REST callback: POST /wp-json/vse/v1/inject-data
     */
    public function rest_inject_data( WP_REST_Request $request ) {
        $video_url  = sanitize_text_field( $request->get_param( 'video_url' ) );
        $post_id    = absint( $request->get_param( 'post_id' ) );
        $post_title = sanitize_text_field( $request->get_param( 'post_title' ) );

        $api_key = self::get_api_key();
        if ( empty( $api_key ) ) {
            return new WP_REST_Response( array(
                'detail' => __( 'Brak skonfigurowanego klucza API VSE. Przejdź do Ustawienia → VSE Video SEO.', 'vse-video-seo' ),
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
            'api_key'    => $api_key,
            'domain'     => self::get_site_domain(),
            'video_url'  => $video_url,
            'post_title' => $post_title,
            'post_url'   => $post_url,
        ), 90 );

        if ( is_wp_error( $res ) ) {
            return new WP_REST_Response( array(
                'detail' => $res->get_error_message(),
            ), 502 );
        }

        $data = $res['data'];
        $code = $res['status_code'];

        if ( 200 === $code && $post_id > 0 && current_user_can( 'edit_post', $post_id ) ) {
            $schema_json = isset( $data['schema_json'] ) ? $data['schema_json'] : '';
            if ( is_array( $schema_json ) ) {
                $schema_json = wp_json_encode( $schema_json, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
            }

            $chapters_json = isset( $data['chapters'] ) ? wp_json_encode( $data['chapters'], JSON_UNESCAPED_UNICODE ) : '[]';
            $after_score   = isset( $data['after_score'] ) ? (int) $data['after_score'] : 94;

            update_post_meta( $post_id, '_vse_schema_json', $schema_json );
            update_post_meta( $post_id, '_vse_video_url', $video_url );
            update_post_meta( $post_id, '_vse_seo_score', $after_score );
            update_post_meta( $post_id, '_vse_chapters_json', $chapters_json );

            // Sync with RankMath / Yoast / SEOPress
            $seo_title       = isset( $data['seo_title'] ) ? $data['seo_title'] : '';
            $meta_desc       = isset( $data['meta_description'] ) ? $data['meta_description'] : '';
            $focus_keyword   = isset( $data['focus_keyword'] ) ? $data['focus_keyword'] : '';
            $synced_adapters = VSE_SEO_Adapter::update_seo_meta( $post_id, $seo_title, $meta_desc, $focus_keyword );

            $data['wp_saved']        = true;
            $data['synced_adapters'] = $synced_adapters;

            // Update cached quota if returned
            if ( isset( $data['remaining_quota'] ) ) {
                $cached = get_option( 'vse_cached_status', array() );
                if ( is_array( $cached ) ) {
                    $cached['remaining_quota'] = $data['remaining_quota'];
                    $cached['used_this_month'] = $data['used_this_month'] ?? ( $cached['used_this_month'] ?? 0 );
                    update_option( 'vse_cached_status', $cached );
                }
            }
        }

        return new WP_REST_Response( $data, $code );
    }

    /**
     * WP AJAX: Validate API key from Settings page.
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
            'api_key' => $api_key,
            'domain'  => self::get_site_domain(),
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
        $resp = $this->rest_inject_data( $req );
        wp_send_json( $resp->get_data(), $resp->get_status() );
    }

    /**
     * Render Settings -> VSE Video SEO admin page.
     */
    public function render_settings_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        $api_key       = self::get_api_key();
        $api_url       = self::get_api_url();
        $cached_status = get_option( 'vse_cached_status', array() );
        $plan          = isset( $cached_status['plan'] ) ? strtoupper( $cached_status['plan'] ) : 'FREE';
        $quota         = isset( $cached_status['monthly_quota'] ) ? (int) $cached_status['monthly_quota'] : 5;
        $used          = isset( $cached_status['used_this_month'] ) ? (int) $cached_status['used_this_month'] : 0;
        $remaining     = isset( $cached_status['remaining_quota'] ) ? (int) $cached_status['remaining_quota'] : max( 0, $quota - $used );
        $nonce         = wp_create_nonce( 'vse_admin_nonce' );
        ?>
        <div class="wrap" style="max-width: 820px;">
            <h1 style="display:flex;align-items:center;gap:10px;">
                <span class="dashicons dashicons-video-alt3" style="font-size:28px;width:28px;height:28px;color:#e11d48;"></span>
                <?php esc_html_e( 'VSE Video SEO — AI Schema & Chapters', 'vse-video-seo' ); ?>
                <span style="font-size:12px;background:#f1f5f9;color:#475569;padding:2px 8px;border-radius:12px;font-weight:600;">v<?php echo esc_html( VSE_VIDEO_SEO_VERSION ); ?></span>
            </h1>

            <p style="font-size:14px;color:#475569;">
                <?php esc_html_e( 'Automatycznie generuj i wstrzykuj czyste znaczniki JSON-LD (VideoObject + Clip Key Moments + FAQPage) bezpośrednio do sekcji <head> oraz synchronizuj metadane z RankMath, Yoast SEO i SEOPress.', 'vse-video-seo' ); ?>
            </p>

            <!-- Status & Quota Card -->
            <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin:20px 0;box-shadow:0 1px 2px rgba(0,0,0,0.03);">
                <h2 style="margin-top:0;font-size:16px;"><?php esc_html_e( 'Status Licencji i Limit Miesięczny', 'vse-video-seo' ); ?></h2>
                <div id="vse-status-box" style="display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
                    <div>
                        <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Aktywny Plan', 'vse-video-seo' ); ?></span>
                        <strong id="vse-stat-plan" style="font-size:18px;color:#0f172a;"><?php echo esc_html( $plan ); ?></strong>
                    </div>
                    <div>
                        <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Wykorzystano w tym miesiącu', 'vse-video-seo' ); ?></span>
                        <strong id="vse-stat-usage" style="font-size:18px;color:#0f172a;"><?php echo esc_html( $used . ' / ' . ( $quota < 0 ? '∞' : $quota ) ); ?> <?php esc_html_e( 'filmów', 'vse-video-seo' ); ?></strong>
                    </div>
                    <div>
                        <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Pozostały limit', 'vse-video-seo' ); ?></span>
                        <strong id="vse-stat-remaining" style="font-size:18px;color:#16a34a;"><?php echo esc_html( $quota < 0 ? 'Bez limitu' : $remaining ); ?></strong>
                    </div>
                    <div>
                        <span style="font-size:12px;color:#64748b;display:block;"><?php esc_html_e( 'Wykryty adapter SEO', 'vse-video-seo' ); ?></span>
                        <strong style="font-size:14px;color:#334155;"><?php echo esc_html( VSE_SEO_Adapter::detect_active_plugin_label() ); ?></strong>
                    </div>
                </div>
                <p id="vse-validate-msg" style="margin:12px 0 0 0;font-size:13px;display:none;"></p>
            </div>

            <form method="post" action="options.php" style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;">
                <?php settings_fields( 'vse_video_seo_settings' ); ?>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row">
                            <label for="vse_api_key"><?php esc_html_e( 'Klucz API (VSE API Key)', 'vse-video-seo' ); ?></label>
                        </th>
                        <td>
                            <input name="vse_api_key" type="password" id="vse_api_key" value="<?php echo esc_attr( $api_key ); ?>" class="regular-text" placeholder="vse_live_..." autocomplete="off" />
                            <button type="button" class="button button-secondary" id="vse-validate-btn">
                                <?php esc_html_e( 'Sprawdź i połącz klucz', 'vse-video-seo' ); ?>
                            </button>
                            <p class="description">
                                <?php
                                printf(
                                    /* translators: %s link to VSE dashboard */
                                    esc_html__( 'Darmowy klucz API (5 filmów/mies.) wygenerujesz w panelu %s.', 'vse-video-seo' ),
                                    '<a href="https://vse.impresjapr.pl/dashboard" target="_blank" rel="noopener">vse.impresjapr.pl/dashboard</a>'
                                );
                                ?>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">
                            <label for="vse_api_url"><?php esc_html_e( 'Adres serwera VSE API', 'vse-video-seo' ); ?></label>
                        </th>
                        <td>
                            <input name="vse_api_url" type="url" id="vse_api_url" value="<?php echo esc_attr( $api_url ); ?>" class="regular-text" />
                            <p class="description"><?php esc_html_e( 'Domyślnie: https://vse.impresjapr.pl', 'vse-video-seo' ); ?></p>
                        </td>
                    </tr>
                </table>
                <?php submit_button( __( 'Zapisz ustawienia', 'vse-video-seo' ) ); ?>
            </form>

            <!-- Pro Banner CTA -->
            <div style="margin-top:24px;background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);color:#fff;border-radius:10px;padding:24px;display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;">
                <div style="max-width:540px;">
                    <span style="background:#e11d48;color:#fff;font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;text-transform:uppercase;">VSE PRO &amp; AGENCY</span>
                    <h3 style="color:#fff;margin:10px 0 6px 0;font-size:18px;"><?php esc_html_e( 'Chcesz automatycznie zamieniać filmy YouTube w pełne artykuły SEO?', 'vse-video-seo' ); ?></h3>
                    <p style="color:#cbd5e1;margin:0;font-size:13px;line-height:1.5;">
                        <?php esc_html_e( 'Odblokuj do 1000 filmów miesięcznie, generowanie pełnych artykułów z transkrypcji AI, automatyczne screenshoty z wideo (ImageObject), integrację z Google Search Console oraz publikację 1-klikiem na wielu portalach.', 'vse-video-seo' ); ?>
                    </p>
                </div>
                <div>
                    <a href="https://vse.impresjapr.pl/#pricing" target="_blank" rel="noopener" class="button button-primary" style="background:#e11d48;border-color:#e11d48;padding:6px 18px;font-weight:600;height:auto;">
                        <?php esc_html_e( 'Zobacz plany Pro →', 'vse-video-seo' ); ?>
                    </a>
                </div>
            </div>
        </div>

        <script>
        (function() {
            var btn = document.getElementById('vse-validate-btn');
            var msg = document.getElementById('vse-validate-msg');
            if (!btn) return;
            btn.addEventListener('click', function() {
                var keyInput = document.getElementById('vse_api_key');
                var urlInput = document.getElementById('vse_api_url');
                btn.disabled = true;
                btn.textContent = 'Sprawdzanie...';
                msg.style.display = 'block';
                msg.style.color = '#475569';
                msg.textContent = 'Łączenie z VSE API...';

                var formData = new FormData();
                formData.append('action', 'vse_validate_key');
                formData.append('nonce', <?php echo wp_json_encode( $nonce ); ?>);
                formData.append('api_key', keyInput ? keyInput.value : '');
                formData.append('api_url', urlInput ? urlInput.value : '');

                fetch(ajaxurl, { method: 'POST', body: formData })
                    .then(function(r) { return r.json(); })
                    .then(function(res) {
                        btn.disabled = false;
                        btn.textContent = 'Sprawdź i połącz klucz';
                        if (res.success && res.data) {
                            var d = res.data;
                            document.getElementById('vse-stat-plan').textContent = (d.plan || 'free').toUpperCase();
                            var q = d.monthly_quota < 0 ? '∞' : d.monthly_quota;
                            document.getElementById('vse-stat-usage').textContent = (d.used_this_month || 0) + ' / ' + q + ' filmów';
                            document.getElementById('vse-stat-remaining').textContent = d.monthly_quota < 0 ? 'Bez limitu' : d.remaining_quota;
                            msg.style.color = '#16a34a';
                            msg.textContent = '✓ Klucz aktywny! Połączono z domeną: ' + (d.allowed_domain || window.location.hostname);
                        } else {
                            var err = (res.data && (res.data.detail || res.data.message)) || 'Nieprawidłowy klucz API.';
                            msg.style.color = '#dc2626';
                            msg.textContent = '✕ Błąd walidacji: ' + err;
                        }
                    })
                    .catch(function(e) {
                        btn.disabled = false;
                        btn.textContent = 'Sprawdź i połącz klucz';
                        msg.style.color = '#dc2626';
                        msg.textContent = '✕ Błąd połączenia: ' + e.message;
                    });
            });
        })();
        </script>
        <?php
    }
}

VSE_Video_SEO::get_instance();
