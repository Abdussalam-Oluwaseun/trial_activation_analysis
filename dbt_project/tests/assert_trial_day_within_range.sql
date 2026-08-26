-- trial_day must be within [0, 29] for every event
select *
from {{ ref('stg_trial_events') }}
where trial_day < 0 or trial_day > 29
