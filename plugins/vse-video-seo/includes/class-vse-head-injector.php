<?php
/**
 * VSE Clean Head Injector — outputs JSON-LD schema directly in <head>.
 *
 * CO: Wstrzykuje zapisany w meta pola `_vse_schema_json` pakiet Schema.org
 *     (VideoObject + Clip + FAQPage) bezpośrednio w sekcji <head> przez hook `wp_head`.
 * PO CO: Domyślny edytor WordPress i filtr `wp_kses_post` wycinają znaczniki
 *        `<script type="application/ld+json">` z treści wpisu (`post_content`).
 *        Wstrzykiwanie w `<head>` z priorytetem 5 gwarantuje 100% nienaruszalność
 *        struktury JSON-LD dla Googlebota.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class VSE_Head_Injector {

    /**
     * Register wp_head action with priority 5.
     */
    public static function init() {
        add_action( 'wp_head', array( __CLASS__, 'render_schema_in_head' ), 5 );
    }

    /**
     * Output validated JSON-LD script blocks in <head> on singular posts/pages.
     */
    public static function render_schema_in_head() {
        if ( ! is_singular() ) {
            return;
        }

        $post_id = get_queried_object_id();
        if ( ! $post_id ) {
            return;
        }

        $raw_schema = get_post_meta( $post_id, '_vse_schema_json', true );
        if ( empty( $raw_schema ) ) {
            return;
        }

        // Validate JSON before rendering so broken JSON-LD is never output
        $decoded = is_string( $raw_schema ) ? json_decode( $raw_schema, true ) : $raw_schema;
        if ( empty( $decoded ) || ( is_string( $raw_schema ) && JSON_ERROR_NONE !== json_last_error() ) ) {
            return;
        }

        echo "\n<!-- VSE Video SEO Engine v" . esc_html( VSE_VIDEO_SEO_VERSION ) . " — Clean Head JSON-LD -->\n";

        // Support both a list of schema objects (VideoObject, FAQPage) and a single schema object
        if ( isset( $decoded[0] ) && is_array( $decoded[0] ) ) {
            foreach ( $decoded as $schema_block ) {
                if ( is_array( $schema_block ) && ! empty( $schema_block['@type'] ) ) {
                    $clean_json = wp_json_encode( $schema_block, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
                    if ( $clean_json ) {
                        // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- JSON validated via json_decode + wp_json_encode, bypassing wp_kses_post intentionally
                        echo '<script type="application/ld+json">' . $clean_json . '</script>' . "\n";
                    }
                }
            }
        } elseif ( is_array( $decoded ) ) {
            $clean_json = wp_json_encode( $decoded, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
            if ( $clean_json ) {
                // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
                echo '<script type="application/ld+json">' . $clean_json . '</script>' . "\n";
            }
        }

        echo "<!-- /VSE Video SEO Engine -->\n";
    }
}
