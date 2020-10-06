create schema solartag;

create materialized view solartag.candidates AS SELECT osm_id, geometry from osm_power_generator, countries.countries where st_intersects(st_transform(countries.wkb_geometry, 3857), geometry) and countries.iso = 'GBR' and ST_GeometryType(geometry) = 'ST_Point' and source = 'solar' and output = '' and tags->'generator:solar:modules' is null;

create unique index solartag_candidates_osm_id on solartag.candidates(osm_id);

CREATE TABLE solartag.users (id INTEGER PRIMARY KEY,
				display_name TEXT NOT NULL,
				token JSONB NOT NULL,
				created TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
			);

CREATE TABLE solartag.results (osm_id BIGINT NOT NULL,
				user_id INTEGER NOT NULL REFERENCES solartag.users(id),
				module_count INTEGER,
				skip_reason TEXT,
				date TIMESTAMP WITHOUT TIME ZONE DEFAULT now());

create unique index results_user_id_osm_id on solartag.results (user_id, osm_id);

-- Given an array of integer results (i.e. module count), which can be null if 
CREATE OR REPLACE FUNCTION solartag.int_decision_arr(data INTEGER[])
RETURNS BOOLEAN IMMUTABLE
AS $$
DECLARE
	skips INTEGER;
	result INTEGER;
BEGIN
	skips := (select count(*) from unnest(data) as value where value is null);

	IF skips > 3 THEN
		RETURN TRUE;
	END IF;
	
	result := solartag.int_decision_value_arr(data);
	IF result IS NOT NULL THEN
		RETURN TRUE;
	ELSE 
		RETURN FALSE;
	END IF;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION solartag.int_decision_value_arr(data INTEGER[])
RETURNS INTEGER IMMUTABLE
AS $$
DECLARE
	threshold NUMERIC;
BEGIN
	threshold := GREATEST((select count(*) from unnest(data) AS value WHERE value IS NOT NULL) * 0.6, 2);
	-- RAISE NOTICE 'threshold for % is %', data, threshold;
	RETURN (SELECT value FROM (
			SELECT value, count(*) FROM unnest(data) AS value
			WHERE value IS NOT NULL
			GROUP BY value
			HAVING count(*) > threshold
			ORDER BY count DESC LIMIT 1
		) a);
END
$$ LANGUAGE plpgsql;


CREATE AGGREGATE solartag.int_decision(INTEGER) (
	sfunc = array_append,
	stype = integer[],
	finalfunc = solartag.int_decision_arr
);

CREATE AGGREGATE solartag.int_decision_value(INTEGER) (
	sfunc = array_append,
	stype = integer[],
	finalfunc = solartag.int_decision_value_arr
);
