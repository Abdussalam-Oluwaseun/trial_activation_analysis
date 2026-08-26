{{
  config(
    materialized = 'table'
  )
}}

/*
  fct_trial_activation — Organisation-level trial activation flag
  ================================================================
  An organisation is "activated" when it completes ALL 5 trial goals
  within its 30-day trial window.

  Grain: one row per organisation.

  Note: Snowflake dialect (`boolor_agg`, `count_if`).
*/

with events as (

    select * from {{ ref('stg_trial_events') }}

),

goals as (

    select * from {{ ref('fct_trial_goals') }}

),

goal_flags as (

    select
        organization_id,
        count(case when is_completed then 1 end) as goals_completed,
        max(case when goal_id = 'g1_scheduling_setup'     and is_completed then 1 else 0 end) as g1_scheduling_setup,
        max(case when goal_id = 'g2_schedule_engagement'  and is_completed then 1 else 0 end) as g2_schedule_engagement,
        max(case when goal_id = 'g3_team_communications'  and is_completed then 1 else 0 end) as g3_team_communications,
        max(case when goal_id = 'g4_punch_clock'          and is_completed then 1 else 0 end) as g4_punch_clock,
        max(case when goal_id = 'g5_sustained_engagement' and is_completed then 1 else 0 end) as g5_sustained_engagement
    from goals
    group by organization_id

),

org_attributes as (

    select
        organization_id,
        min(trial_start)                                as trial_start,
        max(trial_end)                                  as trial_end,
        boolor_agg(converted)                           as converted,
        max(days_to_convert)                            as days_to_convert,
        count(*)                                        as total_events,
        count(distinct date(event_timestamp))           as active_days,
        count_if(activity_name = 'Scheduling.Shift.Created')      as shifts_created,
        count_if(activity_name = 'Scheduling.Availability.Set')   as availability_sets,
        count_if(activity_name = 'Mobile.Schedule.Loaded')        as schedule_views,
        count_if(activity_name = 'Communication.Message.Created') as messages_sent,
        count_if(activity_name = 'PunchClock.PunchedIn')          as punch_ins,
        count_if(activity_name = 'PunchClock.PunchedOut')         as punch_outs
    from events
    group by organization_id

)

select
    a.organization_id,
    a.trial_start,
    a.trial_end,
    a.converted,
    a.days_to_convert,
    a.total_events,
    a.active_days,
    coalesce(g.goals_completed, 0)          as goals_completed,
    coalesce(g.g1_scheduling_setup, 0)      as g1_scheduling_setup,
    coalesce(g.g2_schedule_engagement, 0)   as g2_schedule_engagement,
    coalesce(g.g3_team_communications, 0)   as g3_team_communications,
    coalesce(g.g4_punch_clock, 0)           as g4_punch_clock,
    coalesce(g.g5_sustained_engagement, 0)  as g5_sustained_engagement,
    a.shifts_created,
    a.availability_sets,
    a.schedule_views,
    a.messages_sent,
    a.punch_ins,
    a.punch_outs,
    case when g.goals_completed = 5 then true else false end as is_activated
from org_attributes a
left join goal_flags g
    on a.organization_id = g.organization_id
