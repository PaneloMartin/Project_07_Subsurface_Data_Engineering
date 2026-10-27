{{ config(materialized='view') }}

SELECT
    KGS_ID AS well_id,
    API AS api_number,
    LEASE AS lease_name,
    OPERATOR AS operator_name,
    LATITUDE AS latitude,
    LONGITUDE AS longitude,
    LOCATION AS location_description,
    ELEVATION AS elevation,
    ELEVATION_REFERENCE AS elevation_reference

FROM {{ source('raw', 'wells') }}