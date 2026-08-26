{{
  config(
    materialized = 'table'
  )
}}

/*
  fct_trial_goals — Trial goal completion, one row per organisation per goal
  ===========================================================================
  Evaluates the five trial goals (defined in notebooks/02) against each
  organisation's trial-window events.

  Goals:
    G1  Scheduling Setup     — created >= 1 shift AND set availability
    G2  Schedule Engagement  — viewed the schedule >= 3 times
    G3  Team Communications  — sent >= 1 team message
    G4  Punch Clock          — clocked in/out at least once
    G5  Sustained Engagement — active on >= 5 distinct trial days

  Grain: one row per (organization_id, goal_id).

  Note: Snowflake dialect (`count_if`).
*/

with events as (

    select * from {{ ref('stg_trial_events') }}

),

org_metrics as (

    select
        organization_id,
        count_if(activity_name = 'Scheduling.Shift.Created')      as shifts_created,
        count_if(activity_name = 'Scheduling.Availability.Set')   as availability_sets,
        count_if(activity_name = 'Mobile.Schedule.Loaded')        as schedule_views,
        count_if(activity_name = 'Communication.Message.Created') as messages_sent,
        count_if(activity_name = 'PunchClock.PunchedIn')          as punch_ins,
        count_if(activity_name = 'PunchClock.PunchedOut')         as punch_outs,
        count(distinct date(event_timestamp))                     as active_days
    from events
    group by organization_id

),

goals as (

    select
        organization_id,
        'g1_scheduling_setup'                                     as goal_id,
        'Scheduling Setup'                                        as goal_name,
        'Created at least 1 shift AND set availability'           as goal_description,
        (shifts_created >= 1 and availability_sets >= 1)          as is_completed,
        concat(
            shifts_created, ' shift(s) created, ',
            availability_sets, ' availability set(s)'
        )                                                         as evidence
    from org_metrics

    union all

    select
        organization_id,
        'g2_schedule_engagement'                                  as goal_id,
        'Schedule Engagement'                                     as goal_name,
        'Viewed the schedule at least 3 times (Mobile.Schedule.Loaded)' as goal_description,
        (schedule_views >= 3)                                     as is_completed,
        concat(schedule_views, ' schedule view(s)')               as evidence
    from org_metrics

    union all

    select
        organization_id,
        'g3_team_communications'                                  as goal_id,
        'Team Communications'                                     as goal_name,
        'Sent at least 1 team communication message'              as goal_description,
        (messages_sent >= 1)                                      as is_completed,
        concat(messages_sent, ' message(s) sent')                 as evidence
    from org_metrics

    union all

    select
        organization_id,
        'g4_punch_clock'                                          as goal_id,
        'Punch Clock Activated'                                   as goal_name,
        'Clocked in or out at least once'                         as goal_description,
        (punch_ins >= 1 or punch_outs >= 1)                       as is_completed,
        concat(punch_ins, ' punch-in(s), ', punch_outs, ' punch-out(s)') as evidence
    from org_metrics

    union all

    select
        organization_id,
        'g5_sustained_engagement'                                 as goal_id,
        'Sustained Engagement'                                    as goal_name,
        'Active on at least 5 distinct trial days'                as goal_description,
        (active_days >= 5)                                        as is_completed,
        concat(active_days, ' active day(s)')                     as evidence
    from org_metrics

)

select * from goals
