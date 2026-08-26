-- every organisation must have exactly 5 goal rows in fct_trial_goals
select
    organization_id,
    count(distinct goal_id) as n_goals
from {{ ref('fct_trial_goals') }}
group by 1
having count(distinct goal_id) <> 5
