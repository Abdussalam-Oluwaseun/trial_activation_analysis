{{
  config(
    materialized = 'view'
  )
}}

/*
  stg_trial_events — Cleaned, typed trial event stream
  =====================================================
  Source model: {{ source('trial', 'events') }}

  Expected source columns (raw CSV "DA task.csv" headers are CAPS):

      ORGANIZATION_ID  VARCHAR    -- unique org identifier
      ACTIVITY_NAME    VARCHAR    -- product activity performed
      TIMESTAMP        TIMESTAMP  -- when the activity occurred (UTC)
      CONVERTED        BOOLEAN    -- whether the org converted to paid
      CONVERTED_AT     TIMESTAMP  -- conversion time (NULL if not converted)
      TRIAL_START      TIMESTAMP  -- trial start (UTC)
      TRIAL_END        TIMESTAMP  -- trial end = trial_start + 30 days (UTC)

  Cleaning pipeline (mirrors notebooks/01_data_cleaning_eda.ipynb):
    1. Trim whitespace from string keys
    2. Cast timestamps and the converted boolean
    3. Deduplicate on the event key (organization_id, activity_name, timestamp)
    4. Keep only events inside the trial window [trial_start, trial_end]
    5. Derive trial_day, days_to_convert, module

  Grain: one row per (organization_id, activity_name, timestamp) — a single event.

  Notes:
    - Dialect: Snowflake. For BigQuery swap `count_if`/`boolor_agg`/`datediff`
      for `countif`/`logical_or`/`timestamp_diff` respectively.
    - Timestamps are treated as UTC (as in the source analysis).
*/

with source as (

    select * from {{ source('trial', 'events') }}

),

normalised as (

    select
        trim(organization_id)                       as organization_id,
        trim(activity_name)                         as activity_name,
        cast(timestamp as timestamp)                as event_timestamp,
        cast(converted_at as timestamp)             as converted_at,
        cast(trial_start as timestamp)              as trial_start,
        cast(trial_end as timestamp)                as trial_end,
        coalesce(cast(converted as boolean), false) as converted
    from source

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by organization_id, activity_name, event_timestamp
            order by converted_at nulls last
        ) as event_row_num
    from normalised

),

trial_window as (

    select
        organization_id,
        activity_name,
        event_timestamp,
        converted,
        converted_at,
        trial_start,
        trial_end,
        -- Integer day within the 30-day trial: 0 = first day, 29 = last
        least(datediff(day, trial_start, event_timestamp), 29) as trial_day,
        -- Decimal days from trial start to conversion (NULL for non-converters)
        case
            when converted
                then datediff(millisecond, trial_start, converted_at) / 86400000.0
            else null
        end as days_to_convert
    from deduplicated
    where event_row_num = 1
      and event_timestamp is not null
      and trial_start is not null
      and trial_end is not null
      and event_timestamp >= trial_start
      and event_timestamp <= trial_end

),

with_module as (

    select
        *,
        case
            when activity_name like 'Scheduling%'
              or activity_name like 'Mobile.Schedule%'
              or activity_name like 'Shift%'
                then 'Scheduling'
            when activity_name like 'Absence%'
                then 'Absence'
            when activity_name like 'PunchClock%'
              or activity_name like 'Break%'
                then 'PunchClock'
            when activity_name like 'Timesheets%'
              or activity_name like 'Integration.Xero%'
              or activity_name like 'Revenue%'
                then 'Payroll'
            when activity_name like 'Communication%'
                then 'Communications'
            else 'Other'
        end as module
    from trial_window

)

select * from with_module
