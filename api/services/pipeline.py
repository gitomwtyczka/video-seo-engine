        seo = await asyncio.to_thread(
            generate_schema,
            video_id,
            wp_id_placeholder,
            post_title,
            yt_url,
            vtt_path,  # FIX A: may be None — generator handles it
            api_key,
            None,
            0,
            llm_provider,
            priority_keywords if priority_keywords else None,
            internal_links if internal_links else None,
            site_brand,
            publication_type,
            meta,  # FIX A: pass meta for partial schema (description, duration)
        )