{{ config(materialized='view') }}

SELECT
    w.well_id,
    w.api_number,
    w.lease_name,
    w.operator_name,
    w.latitude,
    w.longitude,

    l.file_id,
    l.depth_start,
    l.depth_stop,

    c.curve_position,
    c.mnemonic,
    c.original_unit,
    c.curve_description,
    c.quality_status

FROM {{ ref('stg_wells') }} AS w

INNER JOIN {{ ref('stg_log_files') }} AS l
    ON w.well_id = l.well_id

INNER JOIN {{ ref('stg_curves') }} AS c
    ON l.file_id = c.file_id