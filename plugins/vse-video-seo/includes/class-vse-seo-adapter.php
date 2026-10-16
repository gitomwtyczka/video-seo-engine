<?php
/**
 * VSE Universal SEO Adapter — synchronizes Title, Meta Description & Focus Keyword
 * across RankMath, Yoast SEO, and SEOPress.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class VSE_SEO_Adapter {

    /**
     * Synchronize generated SEO metadata to RankMath, Yoast SEO, and SEOPress meta keys.
     *
     * @param int    $post_id       WordPress Post ID.
     * @param string $title         Generated SEO Title.
     * @param string $description   Generated Meta Description.
     * @param string $focus_keyword Generated Focus Keyword(s).
     * @return array List of updated SEO plugin adapters.
     */
    public static function update_seo_meta( $post_id, $title, $description, $focus_keyword ) {
        $post_id = absint( $post_id );
        if ( ! $post_id ) {
            return array();
        }

        $title         = sanitize_text_field( (string) $title );
        $description   = sanitize_textarea_field( (string) $description );
        $focus_keyword = sanitize_text_field( (string) $focus_keyword );

        // For Yoast SEO (expects single primary focus keyphrase if comma-separated list is passed)
        $primary_kw = $focus_keyword;
        if ( false !== strpos( $focus_keyword, ',' ) ) {
            $parts      = explode( ',', $focus_keyword );
            $primary_kw = trim( $parts[0] );
        }

        // Write to all three major SEO plugin meta key sets so switching SEO plugins
        // or running headless setups preserves metadata seamlessly.
        if ( '' !== $title ) {
            update_post_meta( $post_id, 'rank_math_title', $title );
            update_post_meta( $post_id, '_yoast_wpseo_title', $title );
            update_post_meta( $post_id, '_seopress_titles_title', $title );
        }

        if ( '' !== $description ) {
            update_post_meta( $post_id, 'rank_math_description', $description );
            update_post_meta( $post_id, '_yoast_wpseo_metadesc', $description );
            update_post_meta( $post_id, '_seopress_titles_desc', $description );
        }

        if ( '' !== $focus_keyword ) {
            update_post_meta( $post_id, 'rank_math_focus_keyword', $focus_keyword );
            update_post_meta( $post_id, '_yoast_wpseo_focuskw', $primary_kw );
            update_post_meta( $post_id, '_seopress_analysis_target_kw', $focus_keyword );
        }

        return self::get_active_adapters();
    }

    /**
     * Detect which SEO plugins are currently active on this WordPress site.
     *
     * @return array
     */
    public static function get_active_adapters() {
        $active = array();
        if ( defined( 'RANK_MATH_VERSION' ) || class_exists( 'RankMath' ) ) {
            $active[] = 'RankMath';
        }
        if ( defined( 'WPSEO_VERSION' ) || class_exists( 'WPSEO_Options' ) ) {
            $active[] = 'Yoast SEO';
        }
        if ( defined( 'SEOPRESS_VERSION' ) || function_exists( 'seopress_init' ) ) {
            $active[] = 'SEOPress';
        }
        if ( empty( $active ) ) {
            $active[] = 'Universal (RankMath + Yoast + SEOPress meta zapisane)';
        }
        return $active;
    }

    /**
     * Human-readable label of active SEO plugin(s).
     *
     * @return string
     */
    public static function detect_active_plugin_label() {
        return implode( ', ', self::get_active_adapters() );
    }
}
