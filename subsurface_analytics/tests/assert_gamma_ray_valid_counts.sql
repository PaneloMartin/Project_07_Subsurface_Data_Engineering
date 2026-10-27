SELECT
    well_id,
    file_id,
    total_measurements,
    valid_measurements
FROM {{ ref('fct_gamma_ray_summary') }}
WHERE valid_measurements > total_measurements
   OR valid_measurements < 0
   OR total_measurements <= 0
   OR valid_measurements IS NULL
   OR total_measurements IS NULL