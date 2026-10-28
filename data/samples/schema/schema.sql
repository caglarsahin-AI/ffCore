-- FFCore demo agent presentation DB (synthetic, package 13a).
-- Aggregates and codes only; no person-level data.

CREATE TABLE departments (
  id integer PRIMARY KEY,
  code varchar(8) NOT NULL UNIQUE,
  name_tr varchar(64) NOT NULL,
  floor smallint NOT NULL,
  bed_capacity integer NOT NULL
);

CREATE TABLE beds (
  id integer PRIMARY KEY,
  department_id integer NOT NULL REFERENCES departments(id),
  bed_code varchar(16) NOT NULL UNIQUE,
  bed_type varchar(16) NOT NULL,
  is_active boolean NOT NULL
);

CREATE TABLE admissions (
  id integer PRIMARY KEY,
  department_id integer NOT NULL REFERENCES departments(id),
  day date NOT NULL,
  admitted_count integer NOT NULL,
  discharged_count integer NOT NULL,
  occupied_beds integer NOT NULL
);

CREATE TABLE devices (
  id integer PRIMARY KEY,
  department_id integer NOT NULL REFERENCES departments(id),
  device_code varchar(16) NOT NULL UNIQUE,
  device_type varchar(32) NOT NULL,
  vendor varchar(128) NOT NULL,
  installed_on date NOT NULL,
  status varchar(16) NOT NULL
);

CREATE TABLE device_faults (
  id integer PRIMARY KEY,
  device_id integer NOT NULL REFERENCES devices(id),
  reported_on date NOT NULL,
  fault_type varchar(32) NOT NULL,
  severity varchar(16) NOT NULL,
  resolved_on date,
  downtime_hours numeric(6,1) NOT NULL
);

CREATE TABLE contracts_meta (
  id integer PRIMARY KEY,
  contract_code varchar(16) NOT NULL UNIQUE,
  title varchar(160) NOT NULL,
  vendor varchar(128) NOT NULL,
  contract_type varchar(32) NOT NULL,
  start_date date NOT NULL,
  end_date date NOT NULL,
  annual_value_try numeric(14,2) NOT NULL,
  notice_days integer NOT NULL,
  file_name varchar(128) NOT NULL
);
