--
-- NOTE:
--
-- File paths need to be edited. Search for $$PATH$$ and
-- replace it with the path to the directory containing
-- the extracted data files.
--
--
-- PostgreSQL database dump
--

-- Dumped from database version 17.4 (Ubuntu 17.4-1.pgdg24.04+2)
-- Dumped by pg_dump version 17.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE postgres;
--
-- Name: postgres; Type: DATABASE; Schema: -; Owner: postgres
--

CREATE DATABASE postgres WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.UTF-8';


ALTER DATABASE postgres OWNER TO postgres;

\connect postgres

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: DATABASE postgres; Type: COMMENT; Schema: -; Owner: postgres
--

COMMENT ON DATABASE postgres IS 'default administrative connection database';


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: halasz
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO halasz;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: halasz
--

COMMENT ON SCHEMA public IS '';


--
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


--
-- Name: digital_twin; Type: SCHEMA; Schema: -; Owner: halasz
--

CREATE SCHEMA digital_twin;


ALTER SCHEMA digital_twin OWNER TO halasz;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: jobstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.jobstatus AS ENUM (
    'queued',
    'processing',
    'done',
    'not_found',
    'error'
);


ALTER TYPE public.jobstatus OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: measurements; Type: TABLE; Schema: public; Owner: halasz
--

CREATE TABLE public.measurements (
    value real,
    "time" timestamp with time zone NOT NULL,
    sensor_id uuid NOT NULL
);


ALTER TABLE public.measurements OWNER TO halasz;

--
-- Name: _hyper_1_1_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: halasz
--

CREATE TABLE _timescaledb_internal._hyper_1_1_chunk (
    CONSTRAINT constraint_1 CHECK ((("time" >= '2025-05-08 02:00:00+02'::timestamp with time zone) AND ("time" < '2025-05-15 02:00:00+02'::timestamp with time zone)))
)
INHERITS (public.measurements);


ALTER TABLE _timescaledb_internal._hyper_1_1_chunk OWNER TO halasz;

--
-- Name: _hyper_1_2_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: halasz
--

CREATE TABLE _timescaledb_internal._hyper_1_2_chunk (
    CONSTRAINT constraint_2 CHECK ((("time" >= '2025-05-15 02:00:00+02'::timestamp with time zone) AND ("time" < '2025-05-22 02:00:00+02'::timestamp with time zone)))
)
INHERITS (public.measurements);


ALTER TABLE _timescaledb_internal._hyper_1_2_chunk OWNER TO halasz;

--
-- Name: _hyper_1_3_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: halasz
--

CREATE TABLE _timescaledb_internal._hyper_1_3_chunk (
    CONSTRAINT constraint_3 CHECK ((("time" >= '2025-08-07 02:00:00+02'::timestamp with time zone) AND ("time" < '2025-08-14 02:00:00+02'::timestamp with time zone)))
)
INHERITS (public.measurements);


ALTER TABLE _timescaledb_internal._hyper_1_3_chunk OWNER TO halasz;

--
-- Name: actuators; Type: TABLE; Schema: digital_twin; Owner: halasz
--

CREATE TABLE digital_twin.actuators (
    id uuid NOT NULL,
    type_id uuid,
    asset_id uuid
);


ALTER TABLE digital_twin.actuators OWNER TO halasz;

--
-- Name: measurement_types; Type: TABLE; Schema: digital_twin; Owner: halasz
--

CREATE TABLE digital_twin.measurement_types (
    id uuid NOT NULL,
    name text,
    unit_id uuid
);


ALTER TABLE digital_twin.measurement_types OWNER TO halasz;

--
-- Name: measurements; Type: TABLE; Schema: digital_twin; Owner: halasz
--

CREATE TABLE digital_twin.measurements (
    value real,
    "time" timestamp with time zone NOT NULL,
    sensor_id uuid NOT NULL
);


ALTER TABLE digital_twin.measurements OWNER TO halasz;

--
-- Name: sensor_types; Type: TABLE; Schema: digital_twin; Owner: halasz
--

CREATE TABLE digital_twin.sensor_types (
    id uuid NOT NULL,
    name text,
    max_value real,
    min_value real,
    measurement_type_id uuid NOT NULL,
    max_accuracy real
);


ALTER TABLE digital_twin.sensor_types OWNER TO halasz;

--
-- Name: sensors; Type: TABLE; Schema: digital_twin; Owner: halasz
--

CREATE TABLE digital_twin.sensors (
    id uuid NOT NULL,
    name text,
    upper_threshold real,
    lower_threshold real,
    measurement_frequency real,
    type_id uuid,
    accuracy real
);


ALTER TABLE digital_twin.sensors OWNER TO halasz;

--
-- Name: units; Type: TABLE; Schema: digital_twin; Owner: halasz
--

CREATE TABLE digital_twin.units (
    id uuid NOT NULL,
    name text
);


ALTER TABLE digital_twin.units OWNER TO halasz;

--
-- Name: actuators; Type: TABLE; Schema: public; Owner: halasz
--

CREATE TABLE public.actuators (
    actuator_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    actuator_type_id uuid,
    asset_id uuid
);


ALTER TABLE public.actuators OWNER TO halasz;

--
-- Name: asset; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.asset (
    asset_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    asset_name text
);


ALTER TABLE public.asset OWNER TO postgres;

--
-- Name: asset_failure_type; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.asset_failure_type (
    asset_failure_type_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    asset_id uuid NOT NULL,
    failure_type_id uuid NOT NULL,
    criticality integer
);


ALTER TABLE public.asset_failure_type OWNER TO postgres;

--
-- Name: asset_failure_type_asset_maintenance_list; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.asset_failure_type_asset_maintenance_list (
    asset_failure_type_asset_maintenance_list_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    asset_failure_type_id uuid NOT NULL,
    asset_maintenance_list_id uuid NOT NULL,
    default_reliability real NOT NULL
);


ALTER TABLE public.asset_failure_type_asset_maintenance_list OWNER TO postgres;

--
-- Name: asset_maintenance_list; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.asset_maintenance_list (
    asset_maintenance_list_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    asset_id uuid NOT NULL,
    maintenance_list_id uuid NOT NULL
);


ALTER TABLE public.asset_maintenance_list OWNER TO postgres;

--
-- Name: eta_beta; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.eta_beta (
    eta_beta_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    eta_value real NOT NULL,
    beta_value real NOT NULL,
    "time" timestamp with time zone NOT NULL,
    asset_failure_type_id uuid NOT NULL
);


ALTER TABLE public.eta_beta OWNER TO postgres;

--
-- Name: failure; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.failure (
    failure_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    failure_name text NOT NULL,
    "time" timestamp with time zone NOT NULL,
    failure_type_id uuid NOT NULL,
    source_sys_time timestamp with time zone NOT NULL,
    failure_start_time timestamp with time zone NOT NULL,
    maintenance_end_time timestamp with time zone NOT NULL
);


ALTER TABLE public.failure OWNER TO postgres;

--
-- Name: failure_type; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.failure_type (
    failure_type_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    failure_type_name text NOT NULL,
    is_preventive boolean NOT NULL
);


ALTER TABLE public.failure_type OWNER TO postgres;

--
-- Name: gamma; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.gamma (
    id uuid NOT NULL,
    "time" timestamp with time zone NOT NULL,
    gamma_value real NOT NULL,
    sensor_failure_type_id uuid NOT NULL,
    contribution real NOT NULL
);


ALTER TABLE public.gamma OWNER TO postgres;

--
-- Name: maintenance_list; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.maintenance_list (
    maintenance_list_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    maintenance_list_name text NOT NULL
);


ALTER TABLE public.maintenance_list OWNER TO postgres;

--
-- Name: measurement_types; Type: TABLE; Schema: public; Owner: halasz
--

CREATE TABLE public.measurement_types (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text,
    unit_id uuid
);


ALTER TABLE public.measurement_types OWNER TO halasz;

--
-- Name: operations_maintenance_list; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.operations_maintenance_list (
    maintenance_list_id uuid NOT NULL,
    operation_id uuid NOT NULL
);


ALTER TABLE public.operations_maintenance_list OWNER TO postgres;

--
-- Name: prediction; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.prediction (
    prediction_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    asset_failure_type_id uuid NOT NULL,
    predicted_reliability real NOT NULL,
    "time" timestamp with time zone NOT NULL,
    prediction_future_time timestamp with time zone NOT NULL
);


ALTER TABLE public.prediction OWNER TO postgres;

--
-- Name: prediction_jobs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.prediction_jobs (
    job_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    request_hash character(64) NOT NULL,
    payload json NOT NULL,
    prediction_id uuid,
    error_message text,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    status public.jobstatus DEFAULT 'queued'::public.jobstatus NOT NULL,
    endpoint_type text NOT NULL
);


ALTER TABLE public.prediction_jobs OWNER TO postgres;

--
-- Name: sensor_failure_type; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sensor_failure_type (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    sensor_id uuid NOT NULL,
    failure_type_id uuid NOT NULL
);


ALTER TABLE public.sensor_failure_type OWNER TO postgres;

--
-- Name: sensor_types; Type: TABLE; Schema: public; Owner: halasz
--

CREATE TABLE public.sensor_types (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text,
    max_value real,
    min_value real,
    measurement_type_id uuid NOT NULL,
    max_accuracy real
);


ALTER TABLE public.sensor_types OWNER TO halasz;

--
-- Name: sensors; Type: TABLE; Schema: public; Owner: halasz
--

CREATE TABLE public.sensors (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text,
    upper_threshold real,
    lower_threshold real,
    measurement_frequency real,
    type_id uuid,
    accuracy real,
    asset_id uuid
);


ALTER TABLE public.sensors OWNER TO halasz;

--
-- Name: test_sensor_data; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.test_sensor_data (
    "time" timestamp with time zone NOT NULL,
    sensor_id integer NOT NULL,
    sensor_data real
);


ALTER TABLE public.test_sensor_data OWNER TO postgres;

--
-- Name: test_sensors; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.test_sensors (
    id integer DEFAULT 1 NOT NULL,
    type character varying(50),
    location character varying(50)
);


ALTER TABLE public.test_sensors OWNER TO postgres;

--
-- Name: test_sensors_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.test_sensors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.test_sensors_id_seq OWNER TO postgres;

--
-- Name: test_sensors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.test_sensors_id_seq OWNED BY public.test_sensors.id;


--
-- Name: units; Type: TABLE; Schema: public; Owner: halasz
--

CREATE TABLE public.units (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text
);


ALTER TABLE public.units OWNER TO halasz;

--
-- Data for Name: hypertable; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.hypertable (id, schema_name, table_name, associated_schema_name, associated_table_prefix, num_dimensions, chunk_sizing_func_schema, chunk_sizing_func_name, chunk_target_size, compression_state, compressed_hypertable_id, status) FROM stdin;
\.
COPY _timescaledb_catalog.hypertable (id, schema_name, table_name, associated_schema_name, associated_table_prefix, num_dimensions, chunk_sizing_func_schema, chunk_sizing_func_name, chunk_target_size, compression_state, compressed_hypertable_id, status) FROM '$$PATH$$/3874.dat';

--
-- Data for Name: chunk; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.chunk (id, hypertable_id, schema_name, table_name, compressed_chunk_id, dropped, status, osm_chunk, creation_time) FROM stdin;
\.
COPY _timescaledb_catalog.chunk (id, hypertable_id, schema_name, table_name, compressed_chunk_id, dropped, status, osm_chunk, creation_time) FROM '$$PATH$$/3880.dat';

--
-- Data for Name: chunk_column_stats; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.chunk_column_stats (id, hypertable_id, chunk_id, column_name, range_start, range_end, valid) FROM stdin;
\.
COPY _timescaledb_catalog.chunk_column_stats (id, hypertable_id, chunk_id, column_name, range_start, range_end, valid) FROM '$$PATH$$/3885.dat';

--
-- Data for Name: dimension; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.dimension (id, hypertable_id, column_name, column_type, aligned, num_slices, partitioning_func_schema, partitioning_func, interval_length, compress_interval_length, integer_now_func_schema, integer_now_func) FROM stdin;
\.
COPY _timescaledb_catalog.dimension (id, hypertable_id, column_name, column_type, aligned, num_slices, partitioning_func_schema, partitioning_func, interval_length, compress_interval_length, integer_now_func_schema, integer_now_func) FROM '$$PATH$$/3876.dat';

--
-- Data for Name: dimension_slice; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.dimension_slice (id, dimension_id, range_start, range_end) FROM stdin;
\.
COPY _timescaledb_catalog.dimension_slice (id, dimension_id, range_start, range_end) FROM '$$PATH$$/3878.dat';

--
-- Data for Name: chunk_constraint; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.chunk_constraint (chunk_id, dimension_slice_id, constraint_name, hypertable_constraint_name) FROM stdin;
\.
COPY _timescaledb_catalog.chunk_constraint (chunk_id, dimension_slice_id, constraint_name, hypertable_constraint_name) FROM '$$PATH$$/3882.dat';

--
-- Data for Name: chunk_index; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.chunk_index (chunk_id, index_name, hypertable_id, hypertable_index_name) FROM stdin;
\.
COPY _timescaledb_catalog.chunk_index (chunk_id, index_name, hypertable_id, hypertable_index_name) FROM '$$PATH$$/3884.dat';

--
-- Data for Name: compression_chunk_size; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.compression_chunk_size (chunk_id, compressed_chunk_id, uncompressed_heap_size, uncompressed_toast_size, uncompressed_index_size, compressed_heap_size, compressed_toast_size, compressed_index_size, numrows_pre_compression, numrows_post_compression, numrows_frozen_immediately) FROM stdin;
\.
COPY _timescaledb_catalog.compression_chunk_size (chunk_id, compressed_chunk_id, uncompressed_heap_size, uncompressed_toast_size, uncompressed_index_size, compressed_heap_size, compressed_toast_size, compressed_index_size, numrows_pre_compression, numrows_post_compression, numrows_frozen_immediately) FROM '$$PATH$$/3897.dat';

--
-- Data for Name: compression_settings; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.compression_settings (relid, compress_relid, segmentby, orderby, orderby_desc, orderby_nullsfirst) FROM stdin;
\.
COPY _timescaledb_catalog.compression_settings (relid, compress_relid, segmentby, orderby, orderby_desc, orderby_nullsfirst) FROM '$$PATH$$/3896.dat';

--
-- Data for Name: continuous_agg; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_agg (mat_hypertable_id, raw_hypertable_id, parent_mat_hypertable_id, user_view_schema, user_view_name, partial_view_schema, partial_view_name, direct_view_schema, direct_view_name, materialized_only, finalized) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_agg (mat_hypertable_id, raw_hypertable_id, parent_mat_hypertable_id, user_view_schema, user_view_name, partial_view_schema, partial_view_name, direct_view_schema, direct_view_name, materialized_only, finalized) FROM '$$PATH$$/3890.dat';

--
-- Data for Name: continuous_agg_migrate_plan; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_agg_migrate_plan (mat_hypertable_id, start_ts, end_ts, user_view_definition) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_agg_migrate_plan (mat_hypertable_id, start_ts, end_ts, user_view_definition) FROM '$$PATH$$/3898.dat';

--
-- Data for Name: continuous_agg_migrate_plan_step; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_agg_migrate_plan_step (mat_hypertable_id, step_id, status, start_ts, end_ts, type, config) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_agg_migrate_plan_step (mat_hypertable_id, step_id, status, start_ts, end_ts, type, config) FROM '$$PATH$$/3899.dat';

--
-- Data for Name: continuous_aggs_bucket_function; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_aggs_bucket_function (mat_hypertable_id, bucket_func, bucket_width, bucket_origin, bucket_offset, bucket_timezone, bucket_fixed_width) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_aggs_bucket_function (mat_hypertable_id, bucket_func, bucket_width, bucket_origin, bucket_offset, bucket_timezone, bucket_fixed_width) FROM '$$PATH$$/3891.dat';

--
-- Data for Name: continuous_aggs_hypertable_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_aggs_hypertable_invalidation_log (hypertable_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_aggs_hypertable_invalidation_log (hypertable_id, lowest_modified_value, greatest_modified_value) FROM '$$PATH$$/3894.dat';

--
-- Data for Name: continuous_aggs_invalidation_threshold; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_aggs_invalidation_threshold (hypertable_id, watermark) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_aggs_invalidation_threshold (hypertable_id, watermark) FROM '$$PATH$$/3892.dat';

--
-- Data for Name: continuous_aggs_materialization_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_aggs_materialization_invalidation_log (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_aggs_materialization_invalidation_log (materialization_id, lowest_modified_value, greatest_modified_value) FROM '$$PATH$$/3895.dat';

--
-- Data for Name: continuous_aggs_watermark; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.continuous_aggs_watermark (mat_hypertable_id, watermark) FROM stdin;
\.
COPY _timescaledb_catalog.continuous_aggs_watermark (mat_hypertable_id, watermark) FROM '$$PATH$$/3893.dat';

--
-- Data for Name: metadata; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.metadata (key, value, include_in_telemetry) FROM stdin;
\.
COPY _timescaledb_catalog.metadata (key, value, include_in_telemetry) FROM '$$PATH$$/3889.dat';

--
-- Data for Name: tablespace; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: postgres
--

COPY _timescaledb_catalog.tablespace (id, hypertable_id, tablespace_name) FROM stdin;
\.
COPY _timescaledb_catalog.tablespace (id, hypertable_id, tablespace_name) FROM '$$PATH$$/3875.dat';

--
-- Data for Name: bgw_job; Type: TABLE DATA; Schema: _timescaledb_config; Owner: postgres
--

COPY _timescaledb_config.bgw_job (id, application_name, schedule_interval, max_runtime, max_retries, retry_period, proc_schema, proc_name, owner, scheduled, fixed_schedule, initial_start, hypertable_id, config, check_schema, check_name, timezone) FROM stdin;
\.
COPY _timescaledb_config.bgw_job (id, application_name, schedule_interval, max_runtime, max_retries, retry_period, proc_schema, proc_name, owner, scheduled, fixed_schedule, initial_start, hypertable_id, config, check_schema, check_name, timezone) FROM '$$PATH$$/3888.dat';

--
-- Data for Name: _hyper_1_1_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: halasz
--

COPY _timescaledb_internal._hyper_1_1_chunk (value, "time", sensor_id) FROM stdin;
\.
COPY _timescaledb_internal._hyper_1_1_chunk (value, "time", sensor_id) FROM '$$PATH$$/4297.dat';

--
-- Data for Name: _hyper_1_2_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: halasz
--

COPY _timescaledb_internal._hyper_1_2_chunk (value, "time", sensor_id) FROM stdin;
\.
COPY _timescaledb_internal._hyper_1_2_chunk (value, "time", sensor_id) FROM '$$PATH$$/4298.dat';

--
-- Data for Name: _hyper_1_3_chunk; Type: TABLE DATA; Schema: _timescaledb_internal; Owner: halasz
--

COPY _timescaledb_internal._hyper_1_3_chunk (value, "time", sensor_id) FROM stdin;
\.
COPY _timescaledb_internal._hyper_1_3_chunk (value, "time", sensor_id) FROM '$$PATH$$/4299.dat';

--
-- Data for Name: actuators; Type: TABLE DATA; Schema: digital_twin; Owner: halasz
--

COPY digital_twin.actuators (id, type_id, asset_id) FROM stdin;
\.
COPY digital_twin.actuators (id, type_id, asset_id) FROM '$$PATH$$/4283.dat';

--
-- Data for Name: measurement_types; Type: TABLE DATA; Schema: digital_twin; Owner: halasz
--

COPY digital_twin.measurement_types (id, name, unit_id) FROM stdin;
\.
COPY digital_twin.measurement_types (id, name, unit_id) FROM '$$PATH$$/4285.dat';

--
-- Data for Name: measurements; Type: TABLE DATA; Schema: digital_twin; Owner: halasz
--

COPY digital_twin.measurements (value, "time", sensor_id) FROM stdin;
\.
COPY digital_twin.measurements (value, "time", sensor_id) FROM '$$PATH$$/4287.dat';

--
-- Data for Name: sensor_types; Type: TABLE DATA; Schema: digital_twin; Owner: halasz
--

COPY digital_twin.sensor_types (id, name, max_value, min_value, measurement_type_id, max_accuracy) FROM stdin;
\.
COPY digital_twin.sensor_types (id, name, max_value, min_value, measurement_type_id, max_accuracy) FROM '$$PATH$$/4284.dat';

--
-- Data for Name: sensors; Type: TABLE DATA; Schema: digital_twin; Owner: halasz
--

COPY digital_twin.sensors (id, name, upper_threshold, lower_threshold, measurement_frequency, type_id, accuracy) FROM stdin;
\.
COPY digital_twin.sensors (id, name, upper_threshold, lower_threshold, measurement_frequency, type_id, accuracy) FROM '$$PATH$$/4282.dat';

--
-- Data for Name: units; Type: TABLE DATA; Schema: digital_twin; Owner: halasz
--

COPY digital_twin.units (id, name) FROM stdin;
\.
COPY digital_twin.units (id, name) FROM '$$PATH$$/4286.dat';

--
-- Data for Name: actuators; Type: TABLE DATA; Schema: public; Owner: halasz
--

COPY public.actuators (actuator_id, actuator_type_id, asset_id) FROM stdin;
\.
COPY public.actuators (actuator_id, actuator_type_id, asset_id) FROM '$$PATH$$/4288.dat';

--
-- Data for Name: asset; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.asset (asset_id, asset_name) FROM stdin;
\.
COPY public.asset (asset_id, asset_name) FROM '$$PATH$$/4310.dat';

--
-- Data for Name: asset_failure_type; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.asset_failure_type (asset_failure_type_id, asset_id, failure_type_id, criticality) FROM stdin;
\.
COPY public.asset_failure_type (asset_failure_type_id, asset_id, failure_type_id, criticality) FROM '$$PATH$$/4303.dat';

--
-- Data for Name: asset_failure_type_asset_maintenance_list; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.asset_failure_type_asset_maintenance_list (asset_failure_type_asset_maintenance_list_id, asset_failure_type_id, asset_maintenance_list_id, default_reliability) FROM stdin;
\.
COPY public.asset_failure_type_asset_maintenance_list (asset_failure_type_asset_maintenance_list_id, asset_failure_type_id, asset_maintenance_list_id, default_reliability) FROM '$$PATH$$/4311.dat';

--
-- Data for Name: asset_maintenance_list; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.asset_maintenance_list (asset_maintenance_list_id, asset_id, maintenance_list_id) FROM stdin;
\.
COPY public.asset_maintenance_list (asset_maintenance_list_id, asset_id, maintenance_list_id) FROM '$$PATH$$/4307.dat';

--
-- Data for Name: eta_beta; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.eta_beta (eta_beta_id, eta_value, beta_value, "time", asset_failure_type_id) FROM stdin;
\.
COPY public.eta_beta (eta_beta_id, eta_value, beta_value, "time", asset_failure_type_id) FROM '$$PATH$$/4304.dat';

--
-- Data for Name: failure; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.failure (failure_id, failure_name, "time", failure_type_id, source_sys_time, failure_start_time, maintenance_end_time) FROM stdin;
\.
COPY public.failure (failure_id, failure_name, "time", failure_type_id, source_sys_time, failure_start_time, maintenance_end_time) FROM '$$PATH$$/4305.dat';

--
-- Data for Name: failure_type; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.failure_type (failure_type_id, failure_type_name, is_preventive) FROM stdin;
\.
COPY public.failure_type (failure_type_id, failure_type_name, is_preventive) FROM '$$PATH$$/4301.dat';

--
-- Data for Name: gamma; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.gamma (id, "time", gamma_value, sensor_failure_type_id, contribution) FROM stdin;
\.
COPY public.gamma (id, "time", gamma_value, sensor_failure_type_id, contribution) FROM '$$PATH$$/4302.dat';

--
-- Data for Name: maintenance_list; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.maintenance_list (maintenance_list_id, maintenance_list_name) FROM stdin;
\.
COPY public.maintenance_list (maintenance_list_id, maintenance_list_name) FROM '$$PATH$$/4308.dat';

--
-- Data for Name: measurement_types; Type: TABLE DATA; Schema: public; Owner: halasz
--

COPY public.measurement_types (id, name, unit_id) FROM stdin;
\.
COPY public.measurement_types (id, name, unit_id) FROM '$$PATH$$/4290.dat';

--
-- Data for Name: measurements; Type: TABLE DATA; Schema: public; Owner: halasz
--

COPY public.measurements (value, "time", sensor_id) FROM stdin;
\.
COPY public.measurements (value, "time", sensor_id) FROM '$$PATH$$/4293.dat';

--
-- Data for Name: operations_maintenance_list; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.operations_maintenance_list (maintenance_list_id, operation_id) FROM stdin;
\.
COPY public.operations_maintenance_list (maintenance_list_id, operation_id) FROM '$$PATH$$/4309.dat';

--
-- Data for Name: prediction; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.prediction (prediction_id, asset_failure_type_id, predicted_reliability, "time", prediction_future_time) FROM stdin;
\.
COPY public.prediction (prediction_id, asset_failure_type_id, predicted_reliability, "time", prediction_future_time) FROM '$$PATH$$/4306.dat';

--
-- Data for Name: prediction_jobs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.prediction_jobs (job_id, request_hash, payload, prediction_id, error_message, created_at, updated_at, status, endpoint_type) FROM stdin;
\.
COPY public.prediction_jobs (job_id, request_hash, payload, prediction_id, error_message, created_at, updated_at, status, endpoint_type) FROM '$$PATH$$/4312.dat';

--
-- Data for Name: sensor_failure_type; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sensor_failure_type (id, sensor_id, failure_type_id) FROM stdin;
\.
COPY public.sensor_failure_type (id, sensor_id, failure_type_id) FROM '$$PATH$$/4300.dat';

--
-- Data for Name: sensor_types; Type: TABLE DATA; Schema: public; Owner: halasz
--

COPY public.sensor_types (id, name, max_value, min_value, measurement_type_id, max_accuracy) FROM stdin;
\.
COPY public.sensor_types (id, name, max_value, min_value, measurement_type_id, max_accuracy) FROM '$$PATH$$/4291.dat';

--
-- Data for Name: sensors; Type: TABLE DATA; Schema: public; Owner: halasz
--

COPY public.sensors (id, name, upper_threshold, lower_threshold, measurement_frequency, type_id, accuracy, asset_id) FROM stdin;
\.
COPY public.sensors (id, name, upper_threshold, lower_threshold, measurement_frequency, type_id, accuracy, asset_id) FROM '$$PATH$$/4292.dat';

--
-- Data for Name: test_sensor_data; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.test_sensor_data ("time", sensor_id, sensor_data) FROM stdin;
\.
COPY public.test_sensor_data ("time", sensor_id, sensor_data) FROM '$$PATH$$/4296.dat';

--
-- Data for Name: test_sensors; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.test_sensors (id, type, location) FROM stdin;
\.
COPY public.test_sensors (id, type, location) FROM '$$PATH$$/4295.dat';

--
-- Data for Name: units; Type: TABLE DATA; Schema: public; Owner: halasz
--

COPY public.units (id, name) FROM stdin;
\.
COPY public.units (id, name) FROM '$$PATH$$/4289.dat';

--
-- Name: chunk_column_stats_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_column_stats_id_seq', 1, false);


--
-- Name: chunk_constraint_name; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_constraint_name', 6, true);


--
-- Name: chunk_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_id_seq', 3, true);


--
-- Name: continuous_agg_migrate_plan_step_step_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.continuous_agg_migrate_plan_step_step_id_seq', 1, false);


--
-- Name: dimension_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_id_seq', 1, true);


--
-- Name: dimension_slice_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_slice_id_seq', 3, true);


--
-- Name: hypertable_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_catalog.hypertable_id_seq', 1, true);


--
-- Name: bgw_job_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_config; Owner: postgres
--

SELECT pg_catalog.setval('_timescaledb_config.bgw_job_id_seq', 1000, false);


--
-- Name: test_sensors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.test_sensors_id_seq', 1, false);


--
-- Name: _hyper_1_1_chunk 1_1_measurements_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: halasz
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk
    ADD CONSTRAINT "1_1_measurements_pkey" PRIMARY KEY ("time", sensor_id);


--
-- Name: _hyper_1_2_chunk 2_3_measurements_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: halasz
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk
    ADD CONSTRAINT "2_3_measurements_pkey" PRIMARY KEY ("time", sensor_id);


--
-- Name: _hyper_1_3_chunk 3_5_measurements_pkey; Type: CONSTRAINT; Schema: _timescaledb_internal; Owner: halasz
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk
    ADD CONSTRAINT "3_5_measurements_pkey" PRIMARY KEY ("time", sensor_id);


--
-- Name: actuators actuators_pkey; Type: CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.actuators
    ADD CONSTRAINT actuators_pkey PRIMARY KEY (id);


--
-- Name: measurement_types measurement_types_pkey; Type: CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.measurement_types
    ADD CONSTRAINT measurement_types_pkey PRIMARY KEY (id);


--
-- Name: measurements measurements_pkey; Type: CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.measurements
    ADD CONSTRAINT measurements_pkey PRIMARY KEY ("time", sensor_id);


--
-- Name: sensor_types sensor_types_pkey; Type: CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.sensor_types
    ADD CONSTRAINT sensor_types_pkey PRIMARY KEY (id);


--
-- Name: sensors sensors_pkey; Type: CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.sensors
    ADD CONSTRAINT sensors_pkey PRIMARY KEY (id);


--
-- Name: units units_pkey; Type: CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.units
    ADD CONSTRAINT units_pkey PRIMARY KEY (id);


--
-- Name: actuators actuators_pkey; Type: CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.actuators
    ADD CONSTRAINT actuators_pkey PRIMARY KEY (actuator_id);


--
-- Name: asset_failure_type_asset_maintenance_list asset_failure_type_asset_maintenance_list_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_failure_type_asset_maintenance_list
    ADD CONSTRAINT asset_failure_type_asset_maintenance_list_pkey PRIMARY KEY (asset_failure_type_asset_maintenance_list_id);


--
-- Name: asset_failure_type asset_failure_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_failure_type
    ADD CONSTRAINT asset_failure_type_pkey PRIMARY KEY (asset_failure_type_id);


--
-- Name: asset_maintenance_list asset_maintenance_list_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_maintenance_list
    ADD CONSTRAINT asset_maintenance_list_pkey PRIMARY KEY (asset_maintenance_list_id);


--
-- Name: asset asset_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_pkey PRIMARY KEY (asset_id);


--
-- Name: eta_beta eta_beta_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.eta_beta
    ADD CONSTRAINT eta_beta_pkey PRIMARY KEY (eta_beta_id, "time");


--
-- Name: failure failure_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.failure
    ADD CONSTRAINT failure_pkey PRIMARY KEY (failure_id, "time");


--
-- Name: failure_type failure_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.failure_type
    ADD CONSTRAINT failure_type_pkey PRIMARY KEY (failure_type_id);


--
-- Name: gamma gamma_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gamma
    ADD CONSTRAINT gamma_pkey PRIMARY KEY (id, "time");


--
-- Name: maintenance_list maintenance_list_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.maintenance_list
    ADD CONSTRAINT maintenance_list_pkey PRIMARY KEY (maintenance_list_id);


--
-- Name: measurement_types measurement_types_pkey; Type: CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.measurement_types
    ADD CONSTRAINT measurement_types_pkey PRIMARY KEY (id);


--
-- Name: measurements measurements_pkey; Type: CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.measurements
    ADD CONSTRAINT measurements_pkey PRIMARY KEY ("time", sensor_id);


--
-- Name: operations_maintenance_list operations_maintenance_list_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.operations_maintenance_list
    ADD CONSTRAINT operations_maintenance_list_pkey PRIMARY KEY (maintenance_list_id, operation_id);


--
-- Name: prediction_jobs prediction_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.prediction_jobs
    ADD CONSTRAINT prediction_jobs_pkey PRIMARY KEY (job_id);


--
-- Name: prediction prediction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.prediction
    ADD CONSTRAINT prediction_pkey PRIMARY KEY (prediction_id, "time");


--
-- Name: sensor_failure_type sensor_failure_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensor_failure_type
    ADD CONSTRAINT sensor_failure_type_pkey PRIMARY KEY (id);


--
-- Name: sensor_types sensor_types_pkey; Type: CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.sensor_types
    ADD CONSTRAINT sensor_types_pkey PRIMARY KEY (id);


--
-- Name: sensors sensors_pkey; Type: CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_pkey PRIMARY KEY (id);


--
-- Name: test_sensor_data test_sensor_data_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.test_sensor_data
    ADD CONSTRAINT test_sensor_data_pkey PRIMARY KEY ("time", sensor_id);


--
-- Name: test_sensors test_sensors_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.test_sensors
    ADD CONSTRAINT test_sensors_pkey PRIMARY KEY (id);


--
-- Name: units units_pkey; Type: CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_pkey PRIMARY KEY (id);


--
-- Name: _hyper_1_1_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: halasz
--

CREATE INDEX _hyper_1_1_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_1_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_2_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: halasz
--

CREATE INDEX _hyper_1_2_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_2_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_3_chunk_measurements_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: halasz
--

CREATE INDEX _hyper_1_3_chunk_measurements_time_idx ON _timescaledb_internal._hyper_1_3_chunk USING btree ("time" DESC);


--
-- Name: measurements_time_idx; Type: INDEX; Schema: public; Owner: halasz
--

CREATE INDEX measurements_time_idx ON public.measurements USING btree ("time" DESC);


--
-- Name: measurements ts_insert_blocker; Type: TRIGGER; Schema: public; Owner: halasz
--

CREATE TRIGGER ts_insert_blocker BEFORE INSERT ON public.measurements FOR EACH ROW EXECUTE FUNCTION _timescaledb_functions.insert_blocker();


--
-- Name: _hyper_1_1_chunk 1_2_sensors; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: halasz
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk
    ADD CONSTRAINT "1_2_sensors" FOREIGN KEY (sensor_id) REFERENCES public.sensors(id);


--
-- Name: _hyper_1_2_chunk 2_4_sensors; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: halasz
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk
    ADD CONSTRAINT "2_4_sensors" FOREIGN KEY (sensor_id) REFERENCES public.sensors(id);


--
-- Name: _hyper_1_3_chunk 3_6_sensors; Type: FK CONSTRAINT; Schema: _timescaledb_internal; Owner: halasz
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk
    ADD CONSTRAINT "3_6_sensors" FOREIGN KEY (sensor_id) REFERENCES public.sensors(id);


--
-- Name: sensor_types measurement_types; Type: FK CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.sensor_types
    ADD CONSTRAINT measurement_types FOREIGN KEY (measurement_type_id) REFERENCES digital_twin.measurement_types(id) NOT VALID;


--
-- Name: sensors sensor_type_id; Type: FK CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.sensors
    ADD CONSTRAINT sensor_type_id FOREIGN KEY (type_id) REFERENCES digital_twin.sensor_types(id) NOT VALID;


--
-- Name: measurements sensors; Type: FK CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.measurements
    ADD CONSTRAINT sensors FOREIGN KEY (sensor_id) REFERENCES digital_twin.sensors(id) NOT VALID;


--
-- Name: measurement_types unit; Type: FK CONSTRAINT; Schema: digital_twin; Owner: halasz
--

ALTER TABLE ONLY digital_twin.measurement_types
    ADD CONSTRAINT unit FOREIGN KEY (unit_id) REFERENCES digital_twin.units(id) NOT VALID;


--
-- Name: eta_beta asset_failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.eta_beta
    ADD CONSTRAINT asset_failure_type_id FOREIGN KEY (asset_failure_type_id) REFERENCES public.asset_failure_type(asset_failure_type_id) NOT VALID;


--
-- Name: prediction asset_failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.prediction
    ADD CONSTRAINT asset_failure_type_id FOREIGN KEY (asset_failure_type_id) REFERENCES public.asset_failure_type(asset_failure_type_id) NOT VALID;


--
-- Name: asset_failure_type_asset_maintenance_list asset_failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_failure_type_asset_maintenance_list
    ADD CONSTRAINT asset_failure_type_id FOREIGN KEY (asset_failure_type_id) REFERENCES public.asset_failure_type(asset_failure_type_id);


--
-- Name: asset_failure_type asset_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_failure_type
    ADD CONSTRAINT asset_id FOREIGN KEY (asset_id) REFERENCES public.asset(asset_id) NOT VALID;


--
-- Name: sensors asset_id; Type: FK CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT asset_id FOREIGN KEY (asset_id) REFERENCES public.asset(asset_id) NOT VALID;


--
-- Name: asset_maintenance_list asset_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_maintenance_list
    ADD CONSTRAINT asset_id FOREIGN KEY (asset_id) REFERENCES public.asset(asset_id) NOT VALID;


--
-- Name: asset_failure_type_asset_maintenance_list asset_maintenance_list_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_failure_type_asset_maintenance_list
    ADD CONSTRAINT asset_maintenance_list_id FOREIGN KEY (asset_maintenance_list_id) REFERENCES public.asset_maintenance_list(asset_maintenance_list_id);


--
-- Name: sensor_failure_type failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensor_failure_type
    ADD CONSTRAINT failure_type_id FOREIGN KEY (failure_type_id) REFERENCES public.failure_type(failure_type_id) NOT VALID;


--
-- Name: asset_failure_type failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_failure_type
    ADD CONSTRAINT failure_type_id FOREIGN KEY (failure_type_id) REFERENCES public.failure_type(failure_type_id) NOT VALID;


--
-- Name: failure failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.failure
    ADD CONSTRAINT failure_type_id FOREIGN KEY (failure_type_id) REFERENCES public.failure_type(failure_type_id) NOT VALID;


--
-- Name: asset_maintenance_list maintenance_list_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.asset_maintenance_list
    ADD CONSTRAINT maintenance_list_id FOREIGN KEY (maintenance_list_id) REFERENCES public.maintenance_list(maintenance_list_id) NOT VALID;


--
-- Name: operations_maintenance_list maintenance_list_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.operations_maintenance_list
    ADD CONSTRAINT maintenance_list_id FOREIGN KEY (maintenance_list_id) REFERENCES public.maintenance_list(maintenance_list_id) NOT VALID;


--
-- Name: sensor_types measurement_types; Type: FK CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.sensor_types
    ADD CONSTRAINT measurement_types FOREIGN KEY (measurement_type_id) REFERENCES public.measurement_types(id);


--
-- Name: gamma sensor_failure_type_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.gamma
    ADD CONSTRAINT sensor_failure_type_id FOREIGN KEY (sensor_failure_type_id) REFERENCES public.sensor_failure_type(id) NOT VALID;


--
-- Name: sensor_failure_type sensor_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sensor_failure_type
    ADD CONSTRAINT sensor_id FOREIGN KEY (sensor_id) REFERENCES public.sensors(id) NOT VALID;


--
-- Name: sensors sensor_type_id; Type: FK CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensor_type_id FOREIGN KEY (type_id) REFERENCES public.sensor_types(id);


--
-- Name: measurements sensors; Type: FK CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.measurements
    ADD CONSTRAINT sensors FOREIGN KEY (sensor_id) REFERENCES public.sensors(id);


--
-- Name: test_sensor_data test_sensor_data_sensor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.test_sensor_data
    ADD CONSTRAINT test_sensor_data_sensor_id_fkey FOREIGN KEY (sensor_id) REFERENCES public.test_sensors(id);


--
-- Name: measurement_types unit; Type: FK CONSTRAINT; Schema: public; Owner: halasz
--

ALTER TABLE ONLY public.measurement_types
    ADD CONSTRAINT unit FOREIGN KEY (unit_id) REFERENCES public.units(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: halasz
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO technical_user;


--
-- Name: TABLE measurements; Type: ACL; Schema: public; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.measurements TO technical_user;


--
-- Name: TABLE _hyper_1_1_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _timescaledb_internal._hyper_1_1_chunk TO technical_user;


--
-- Name: TABLE _hyper_1_2_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _timescaledb_internal._hyper_1_2_chunk TO technical_user;


--
-- Name: TABLE _hyper_1_3_chunk; Type: ACL; Schema: _timescaledb_internal; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE _timescaledb_internal._hyper_1_3_chunk TO technical_user;


--
-- Name: TABLE actuators; Type: ACL; Schema: public; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.actuators TO technical_user;


--
-- Name: TABLE asset; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.asset TO technical_user;


--
-- Name: TABLE asset_failure_type; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.asset_failure_type TO technical_user;


--
-- Name: TABLE asset_failure_type_asset_maintenance_list; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.asset_failure_type_asset_maintenance_list TO technical_user;


--
-- Name: TABLE asset_maintenance_list; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.asset_maintenance_list TO technical_user;


--
-- Name: TABLE eta_beta; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.eta_beta TO technical_user;


--
-- Name: TABLE failure; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.failure TO technical_user;


--
-- Name: TABLE failure_type; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.failure_type TO technical_user;


--
-- Name: TABLE gamma; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.gamma TO technical_user;


--
-- Name: TABLE maintenance_list; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.maintenance_list TO technical_user;


--
-- Name: TABLE measurement_types; Type: ACL; Schema: public; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.measurement_types TO technical_user;


--
-- Name: TABLE operations_maintenance_list; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.operations_maintenance_list TO technical_user;


--
-- Name: TABLE prediction; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.prediction TO technical_user;


--
-- Name: TABLE prediction_jobs; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.prediction_jobs TO technical_user;


--
-- Name: TABLE sensor_failure_type; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.sensor_failure_type TO technical_user;


--
-- Name: TABLE sensor_types; Type: ACL; Schema: public; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.sensor_types TO technical_user;


--
-- Name: TABLE sensors; Type: ACL; Schema: public; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.sensors TO technical_user;


--
-- Name: TABLE test_sensor_data; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.test_sensor_data TO technical_user;


--
-- Name: TABLE test_sensors; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.test_sensors TO technical_user;


--
-- Name: TABLE units; Type: ACL; Schema: public; Owner: halasz
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.units TO technical_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO technical_user;


--
-- PostgreSQL database dump complete
--

