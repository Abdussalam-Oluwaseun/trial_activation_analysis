-- (organization_id, goal_id) must be unique in fct_trial_goals
select
    organization_id,
    goal_id,
    count(*) as row_count
from {{ ref('fct_trial_goals') }}
group by 1, 2
having count(*) > 1
