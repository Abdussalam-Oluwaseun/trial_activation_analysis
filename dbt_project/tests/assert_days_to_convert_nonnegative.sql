-- days_to_convert (when present) must be non-negative
select *
from {{ ref('stg_trial_events') }}
where days_to_convert is not null and days_to_convert < 0
