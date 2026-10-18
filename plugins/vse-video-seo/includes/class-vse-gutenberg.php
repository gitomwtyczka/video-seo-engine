<?php
/**
 * VSE Gutenberg Integration — enqueues the Gutenberg Sidebar UI and passes localized config.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class VSE_Gutenberg {

    /**
     * Initialize Gutenberg hooks.
     */
    public static function init() {
        add_action( 'enqueue_block_editor_assets', array( __CLASS__, 'enqueue_sidebar_assets' ) );
    }

    /**
     * Enqueue Gutenberg sidebar JavaScript and localize configuration.
     */
    public static function enqueue_sidebar_assets() {
        $dependencies = array(
            'wp-plugins',
            'wp-edit-post',
            'wp-element',
            'wp-components',
            'wp-data',
            'wp-api-fetch',
            'wp-i18n',
        );

        wp_enqueue_script(
            'vse-gutenberg-sidebar',
            VSE_VIDEO_SEO_URL . 'assets/js/gutenberg-sidebar.js',
            $dependencies,
            VSE_VIDEO_SEO_VERSION,
            true
        );

        $cached_status = get_option( 'vse_cached_status', array() );
        $api_key       = VSE_Video_SEO::get_api_key();

        wp_localize_script(
            'vse-gutenberg-sidebar',
            'vseEditorConfig',
            array(
                'restUrl'       => esc_url_raw( rest_url( 'vse/v1/' ) ),
                'ajaxUrl'       => esc_url_raw( admin_url( 'admin-ajax.php' ) ),
                'nonce'         => wp_create_nonce( 'wp_rest' ),
                'editorNonce'   => wp_create_nonce( 'vse_editor_nonce' ),
                'hasApiKey'     => ! empty( $api_key ),
                'settingsUrl'   => esc_url_raw( admin_url( 'admin.php?page=vse-video-seo&tab=connection' ) ),
                'generatorUrl'  => esc_url_raw( admin_url( 'admin.php?page=vse-video-seo&tab=generate' ) ),
                'historyUrl'    => esc_url_raw( admin_url( 'admin.php?page=vse-video-seo&tab=history' ) ),
                'registerUrl'   => 'https://vse.impresjapr.pl/register?utm_source=wp_plugin',
                'pricingUrl'    => 'https://vse.impresjapr.pl/cennik',
                'topupUrl'      => 'https://vse.impresjapr.pl/cennik#topup',
                'dashboardUrl'  => 'https://vse.impresjapr.pl/dashboard',
                'activeAdapter' => VSE_SEO_Adapter::detect_active_plugin_label(),
                'cachedStatus'  => is_array( $cached_status ) ? $cached_status : array(),
                'pluginVersion' => VSE_VIDEO_SEO_VERSION,
            )
        );
    }
}
