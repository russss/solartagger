create schema solartag;

create materialized view solartag.candidates AS SELECT osm_id, geometry from osm_power_generator, countries.countries where st_intersects(st_transform(countries.wkb_geometry, 3857), geometry) and countries.iso = 'GBR' and ST_GeometryType(geometry) = 'ST_Point' and source = 'solar' and output = '' and tags->'generator:solar:modules' is null;

create index solartag_candidates_osm_id on solartag.candidates(osm_id);

CREATE TABLE solartag.users (id INTEGER PRIMARY KEY,
				display_name TEXT NOT NULL,
				token JSONB NOT NULL);

CREATE TABLE solartag.results (osm_id BIGINT NOT NULL,
				user_id INTEGER NOT NULL REFERENCES solartag.users(id),
				module_count INTEGER,
				skip_reason TEXT,
				date TIMESTAMP WITHOUT TIME ZONE DEFAULT now());

create index results_user_id on solartag.results (user_id);
