-- every event timestamp must fall within its org's trial window
select *
from {{ ref('stg_trial_events') }}
where event_timestamp < trial_start or event_timestamp > trial_end
