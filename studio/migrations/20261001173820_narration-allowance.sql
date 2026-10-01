-- Keep admission and early narration visibility on the same limit definition.
-- Existing limits are unchanged. uid is intentionally available for a future
-- explicitly authorized per-member override; this migration adds no override.
CREATE FUNCTION public.vp_allowance_limits(uid uuid, resource text)
RETURNS TABLE(user_limit bigint, global_limit bigint)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
 SELECT limits.user_limit,limits.global_limit
 FROM (VALUES
  ('compute',3600::bigint,7200::bigint),
  ('storage',5000000000::bigint,6000000000::bigint),
  ('transcribe',1800::bigint,9000::bigint),
  ('narrate',2000::bigint,10000::bigint)
 ) AS limits(resource,user_limit,global_limit)
 WHERE limits.resource=$2
$$;
REVOKE ALL ON FUNCTION public.vp_allowance_limits(uuid,text) FROM PUBLIC,anon,authenticated;

CREATE OR REPLACE FUNCTION public.vp_reserve(uid uuid, resource text, quantity bigint, rid text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE existing uuid; user_limit bigint; global_limit bigint; total bigint; own bigint; result uuid;
BEGIN
 PERFORM pg_advisory_xact_lock(740930);
 IF NOT EXISTS(SELECT 1 FROM public.vp_members WHERE id=uid AND active) THEN RAISE EXCEPTION 'Active invitation required'; END IF;
 IF quantity<0 THEN RAISE EXCEPTION 'Invalid allowance'; END IF;
 SELECT id INTO existing FROM public.vp_usage WHERE owner=uid AND kind=resource AND request_id=rid;
 IF existing IS NOT NULL THEN RETURN existing; END IF;
 SELECT limits.user_limit,limits.global_limit INTO user_limit,global_limit
 FROM public.vp_allowance_limits(uid,resource) limits;
 IF NOT FOUND THEN RAISE EXCEPTION 'Unknown allowance'; END IF;
 SELECT coalesce(sum(amount),0),coalesce(sum(amount) FILTER(WHERE owner=uid),0) INTO total,own FROM public.vp_usage
 WHERE kind=resource AND (resource='storage' OR created >= date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC');
 IF own+quantity>user_limit OR total+quantity>global_limit THEN RAISE EXCEPTION '% allowance reached',resource; END IF;
 INSERT INTO public.vp_usage(owner,kind,amount,request_id) VALUES(uid,resource,quantity,rid) RETURNING id INTO result;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.vp_reserve(uuid,text,bigint,text) FROM PUBLIC,anon,authenticated;

-- Coordinator-only read: return aggregate capacity, never other users' rows.
-- Unsettled reservations remain charged exactly as vp_reserve charges them.
CREATE FUNCTION public.vp_narration_allowance(uid uuid)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 user_limit bigint; global_limit bigint;
 own_committed bigint; own_reserved bigint; total_committed bigint; total_reserved bigint;
 day_start timestamptz := date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
 reset_at timestamptz := (date_trunc('day',now() AT TIME ZONE 'UTC') + interval '1 day') AT TIME ZONE 'UTC';
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.vp_members WHERE id=uid AND active) THEN RAISE EXCEPTION 'Active invitation required'; END IF;
 SELECT limits.user_limit,limits.global_limit INTO user_limit,global_limit
 FROM public.vp_allowance_limits(uid,'narrate') limits;
 IF NOT FOUND THEN RAISE EXCEPTION 'Narration allowance unavailable'; END IF;
 SELECT
  coalesce(sum(amount) FILTER(WHERE owner=uid AND settled IS TRUE),0),
  coalesce(sum(amount) FILTER(WHERE owner=uid AND settled IS NOT TRUE),0),
  coalesce(sum(amount) FILTER(WHERE settled IS TRUE),0),
  coalesce(sum(amount) FILTER(WHERE settled IS NOT TRUE),0)
 INTO own_committed,own_reserved,total_committed,total_reserved
 FROM public.vp_usage WHERE kind='narrate' AND created>=day_start;
 RETURN jsonb_build_object(
  'checked_at',now(),'resets_at',reset_at,
  'user',jsonb_build_object('limit',user_limit,'committed',own_committed,'reserved',own_reserved),
  'shared',jsonb_build_object('limit',global_limit,'committed',total_committed,'reserved',total_reserved)
 );
END $$;
REVOKE ALL ON FUNCTION public.vp_narration_allowance(uuid) FROM PUBLIC,anon,authenticated;
