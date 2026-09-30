CREATE TABLE public.vp_members (
 id uuid PRIMARY KEY REFERENCES auth.users(id), email text NOT NULL,
 active boolean NOT NULL DEFAULT true, is_owner boolean NOT NULL DEFAULT false,
 created timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.vp_kv (kind text NOT NULL,key text NOT NULL,value text NOT NULL,expires double precision,PRIMARY KEY(kind,key));
CREATE TABLE public.vp_projects (
 id uuid PRIMARY KEY,owner uuid NOT NULL REFERENCES public.vp_members(id),title text NOT NULL,
 checkpoint text, sandbox_id text, touched double precision NOT NULL DEFAULT 0,
 created timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.vp_objects (
 id uuid PRIMARY KEY,owner uuid NOT NULL REFERENCES public.vp_members(id),project uuid NOT NULL REFERENCES public.vp_projects(id),
 kind text NOT NULL CHECK(kind IN ('source','checkpoint','video','archive','review')),
 name text NOT NULL,key text NOT NULL UNIQUE,url text NOT NULL,size bigint NOT NULL CHECK(size>=0),
 usage_id uuid,created timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.vp_tasks (
 id uuid PRIMARY KEY,owner uuid NOT NULL REFERENCES public.vp_members(id),project uuid NOT NULL REFERENCES public.vp_projects(id),
 operation text NOT NULL,request_id text NOT NULL, payload jsonb NOT NULL,
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
 result jsonb,error text,usage_id uuid,created timestamptz NOT NULL DEFAULT now(),updated timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner,request_id)
);
CREATE UNIQUE INDEX vp_one_task_per_project ON public.vp_tasks(project) WHERE status IN ('queued','running');
CREATE TABLE public.vp_events (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,task uuid NOT NULL REFERENCES public.vp_tasks(id),owner uuid NOT NULL,message text NOT NULL,created timestamptz DEFAULT now());
CREATE TABLE public.vp_revisions (id uuid PRIMARY KEY,project uuid NOT NULL REFERENCES public.vp_projects(id),owner uuid NOT NULL,video uuid NOT NULL REFERENCES public.vp_objects(id),archive uuid NOT NULL REFERENCES public.vp_objects(id),summary text NOT NULL,metadata jsonb NOT NULL,created timestamptz DEFAULT now());
CREATE TABLE public.vp_usage (id uuid PRIMARY KEY DEFAULT gen_random_uuid(),owner uuid NOT NULL REFERENCES public.vp_members(id),kind text NOT NULL,amount bigint NOT NULL CHECK(amount>=0),request_id text NOT NULL,settled boolean DEFAULT false,created timestamptz DEFAULT now(),UNIQUE(owner,kind,request_id));
CREATE INDEX ON public.vp_projects(owner);
CREATE INDEX ON public.vp_objects(owner,project);
CREATE INDEX ON public.vp_tasks(owner,created);
CREATE INDEX ON public.vp_events(task,id);
CREATE INDEX ON public.vp_revisions(owner,project);
CREATE INDEX ON public.vp_usage(kind,created);

CREATE FUNCTION public.vp_active() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM public.vp_members WHERE id=(SELECT auth.uid()) AND active)
$$;
REVOKE ALL ON FUNCTION public.vp_active() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.vp_active() TO authenticated;
DO $$ DECLARE t text; p record; BEGIN
 FOREACH t IN ARRAY ARRAY['vp_members','vp_kv','vp_projects','vp_objects','vp_tasks','vp_events','vp_revisions','vp_usage'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON public.%I FROM anon,authenticated',t);
  FOR p IN SELECT policyname FROM pg_policies WHERE schemaname='public' AND tablename=t LOOP
   EXECUTE format('DROP POLICY %I ON public.%I',p.policyname,t);
  END LOOP;
  IF t <> 'vp_kv' THEN
   EXECUTE format('GRANT SELECT ON public.%I TO authenticated',t);
   EXECUTE format('CREATE POLICY owner_read ON public.%I FOR SELECT TO authenticated USING (%I=(SELECT auth.uid()) AND (SELECT public.vp_active()))',t,CASE WHEN t='vp_members' THEN 'id' ELSE 'owner' END);
  END IF;
 END LOOP;
END $$;
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
-- Pilot object access is exclusively through the coordinator. Prevent policies
-- belonging to another bucket from allowing direct pilot uploads or reads.
CREATE POLICY vp_storage_private ON storage.objects AS RESTRICTIVE FOR ALL TO anon,authenticated
 USING(bucket <> 'video-pilot') WITH CHECK(bucket <> 'video-pilot');

CREATE FUNCTION public.vp_admit(uid uuid, user_email text, owner_access boolean) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(740930);
 IF EXISTS(SELECT 1 FROM public.vp_members WHERE id=uid) THEN RETURN; END IF;
 IF NOT owner_access AND (SELECT count(*) FROM public.vp_members WHERE NOT is_owner)>=5 THEN RAISE EXCEPTION 'The five tester pilot is full'; END IF;
 INSERT INTO public.vp_members(id,email,is_owner) VALUES(uid,user_email,owner_access);
END $$;
REVOKE ALL ON FUNCTION public.vp_admit(uuid,text,boolean) FROM PUBLIC,anon,authenticated;

CREATE FUNCTION public.vp_reserve(uid uuid, resource text, quantity bigint, rid text) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE existing uuid; user_limit bigint; global_limit bigint; total bigint; own bigint; result uuid;
BEGIN
 PERFORM pg_advisory_xact_lock(740930);
 IF NOT EXISTS(SELECT 1 FROM public.vp_members WHERE id=uid AND active) THEN RAISE EXCEPTION 'Active invitation required'; END IF;
 IF quantity<0 THEN RAISE EXCEPTION 'Invalid allowance'; END IF;
 SELECT id INTO existing FROM public.vp_usage WHERE owner=uid AND kind=resource AND request_id=rid;
 IF existing IS NOT NULL THEN RETURN existing; END IF;
 CASE resource
 WHEN 'compute' THEN user_limit:=3600;global_limit:=7200;
 WHEN 'storage' THEN user_limit:=5000000000;global_limit:=6000000000;
 WHEN 'transcribe' THEN user_limit:=1800;global_limit:=9000;
 WHEN 'narrate' THEN user_limit:=2000;global_limit:=10000;
 ELSE RAISE EXCEPTION 'Unknown allowance'; END CASE;
 SELECT coalesce(sum(amount),0),coalesce(sum(amount) FILTER(WHERE owner=uid),0) INTO total,own FROM public.vp_usage
 WHERE kind=resource AND (resource='storage' OR created >= date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC');
 IF own+quantity>user_limit OR total+quantity>global_limit THEN RAISE EXCEPTION '% allowance reached',resource; END IF;
 INSERT INTO public.vp_usage(owner,kind,amount,request_id) VALUES(uid,resource,quantity,rid) RETURNING id INTO result;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.vp_reserve(uuid,text,bigint,text) FROM PUBLIC,anon,authenticated;
