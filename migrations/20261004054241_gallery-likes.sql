-- Anonymous likes are written only by the website server. Public clients cannot
-- read browser hashes or edit counts; counts are always derived from real rows.
CREATE TABLE public.video_likes (
  example_id text NOT NULL CHECK (example_id ~ '^[a-z0-9_-]{1,120}$'),
  visitor_hash text NOT NULL CHECK (visitor_hash ~ '^[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (example_id, visitor_hash)
);
ALTER TABLE public.video_likes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.video_likes FROM PUBLIC, anon, authenticated;

CREATE FUNCTION public.get_video_likes(example_ids text[], viewer_hash text)
RETURNS TABLE (example_id text, like_count integer, liked boolean)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = pg_catalog, public, pg_temp
AS $$
  SELECT requested.id, count(v.visitor_hash)::integer,
    coalesce(bool_or(v.visitor_hash = viewer_hash), false)
  FROM (SELECT DISTINCT unnest(example_ids[1:300]) AS id) requested
  LEFT JOIN public.video_likes v ON v.example_id = requested.id
  GROUP BY requested.id;
$$;
REVOKE ALL ON FUNCTION public.get_video_likes(text[], text) FROM PUBLIC, anon, authenticated;

CREATE FUNCTION public.set_video_like(target_id text, viewer_hash text, is_liked boolean)
RETURNS TABLE (example_id text, like_count integer, liked boolean)
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
  IF is_liked IS NULL THEN RAISE EXCEPTION 'like state required'; END IF;
  -- Serialize simultaneous requests for the same browser/film pair. Explicit
  -- desired state + a unique key make retries idempotent, including unlike.
  PERFORM pg_advisory_xact_lock(hashtextextended(target_id || ':' || viewer_hash, 0));
  IF is_liked THEN
    INSERT INTO public.video_likes (example_id, visitor_hash)
    VALUES (target_id, viewer_hash) ON CONFLICT DO NOTHING;
  ELSE
    DELETE FROM public.video_likes v WHERE v.example_id = target_id AND v.visitor_hash = viewer_hash;
  END IF;
  RETURN QUERY SELECT * FROM public.get_video_likes(ARRAY[target_id], viewer_hash);
END;
$$;
REVOKE ALL ON FUNCTION public.set_video_like(text, text, boolean) FROM PUBLIC, anon, authenticated;
