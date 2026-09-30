ALTER TABLE public.vp_objects DROP CONSTRAINT vp_objects_kind_check;
ALTER TABLE public.vp_objects ADD CONSTRAINT vp_objects_kind_check CHECK(kind IN ('source','checkpoint','video','archive','review','speech'));
