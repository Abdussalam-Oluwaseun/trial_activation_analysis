-- goals_completed must be within [0, 5] for every org
select *
from {{ ref('fct_trial_activation') }}
where goals_completed < 0 or goals_completed > 5
