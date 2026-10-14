-- Stage 6: budgets, transactions, sponsorship, advertising inventory, stadium income,
-- academy fees, and executive reporting views.

begin;

create table budgets (
  organisation_id uuid not null references organisations (id) on delete cascade,
  fiscal_year     integer not null,
  category        text not null check (category in ('player_wages', 'staff_wages', 'transfers', 'operations', 'facilities', 'travel', 'medical', 'academy', 'marketing', 'other')),
  currency        char(3) not null,
  amount          numeric(14, 2) not null check (amount >= 0),
  primary key (organisation_id, fiscal_year, category)
);

-- Signed amounts: income positive, costs negative.
create table financial_transactions (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  occurred_on     date not null,
  fiscal_year     integer not null,
  category        text not null check (category in (
    'player_wages', 'staff_wages', 'transfers', 'operations', 'facilities', 'travel', 'medical', 'academy', 'marketing', 'other',
    'sponsorship_income', 'advertising_income', 'matchday_income', 'stadium_hire_income', 'academy_fees_income', 'transfer_income', 'broadcast_income', 'other_income')),
  currency        char(3) not null,
  amount          numeric(14, 2) not null,
  description     text not null,
  counterparty    text,
  player_id       uuid references players (id),
  contract_id     uuid references contracts (id)
);

create index financial_transactions_org_idx on financial_transactions (organisation_id, fiscal_year, category);

create table sponsors (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  name            text not null,
  industry        text,
  contact_name    text,
  contact_email   text
);

create table sponsorship_deals (
  id          uuid primary key default gen_random_uuid(),
  sponsor_id  uuid not null references sponsors (id) on delete cascade,
  tier        text not null check (tier in ('principal', 'kit', 'official_partner', 'supplier', 'academy', 'community')),
  starts_on   date not null,
  ends_on     date not null,
  currency    char(3) not null,
  annual_value numeric(14, 2) not null check (annual_value >= 0),
  -- e.g. [{"item": "front of shirt"}, {"item": "4 hospitality boxes", "per": "match"}]
  deliverables jsonb not null default '[]',
  status      text not null default 'active' check (status in ('negotiating', 'active', 'expired', 'cancelled')),
  check (ends_on > starts_on)
);

create table ad_inventory (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  name            text not null,
  kind            text not null check (kind in ('led_board', 'static_board', 'shirt', 'training_kit', 'digital', 'matchday_programme', 'naming_rights', 'hospitality')),
  units_available integer not null check (units_available > 0),
  rate_card_price numeric(14, 2) not null,
  currency        char(3) not null
);

create table ad_bookings (
  id           uuid primary key default gen_random_uuid(),
  inventory_id uuid not null references ad_inventory (id) on delete cascade,
  deal_id      uuid references sponsorship_deals (id),
  advertiser   text not null,
  starts_on    date not null,
  ends_on      date not null,
  units        integer not null check (units > 0),
  price        numeric(14, 2) not null,
  check (ends_on >= starts_on)
);

create table stadium_events (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  facility_id     uuid references facilities (id),
  match_id        uuid references matches (id),
  event_date      date not null,
  kind            text not null check (kind in ('home_match', 'concert', 'conference', 'community', 'other')),
  attendance      integer,
  capacity        integer,
  currency        char(3) not null,
  ticket_revenue      numeric(14, 2) not null default 0,
  hospitality_revenue numeric(14, 2) not null default 0,
  concessions_revenue numeric(14, 2) not null default 0,
  operating_cost      numeric(14, 2) not null default 0
);

create table academy_fees (
  id              uuid primary key default gen_random_uuid(),
  registration_id uuid not null references academy_registrations (id) on delete cascade,
  description     text not null,
  currency        char(3) not null,
  amount          numeric(14, 2) not null check (amount >= 0),
  due_on          date not null,
  status          text not null default 'due' check (status in ('due', 'paid', 'overdue', 'waived'))
);

create table payments (
  id            uuid primary key default gen_random_uuid(),
  academy_fee_id uuid references academy_fees (id) on delete set null,
  paid_on       date not null,
  currency      char(3) not null,
  amount        numeric(14, 2) not null check (amount > 0),
  method        text not null check (method in ('card', 'bank_transfer', 'cash', 'direct_debit', 'upi', 'other')),
  reference     text
);

-- ---------------------------------------------------------------------------
-- Executive reporting
-- ---------------------------------------------------------------------------

-- Annual cost of each active player contract: salary plus fees amortised over its length.
create view v_player_contract_costs as
select
  c.organisation_id,
  c.player_id,
  c.id as contract_id,
  c.currency,
  c.annual_salary,
  round((c.transfer_fee + c.signing_fee) / greatest((c.ends_on - c.starts_on) / 365.25, 1), 2) as annual_amortisation,
  c.annual_salary
    + round((c.transfer_fee + c.signing_fee) / greatest((c.ends_on - c.starts_on) / 365.25, 1), 2) as annual_cost,
  c.ends_on
from contracts c
where c.status = 'active';

create view v_wage_bill as
select organisation_id, currency, count(*) as players, sum(annual_salary) as annual_wages,
       sum(annual_cost) as annual_cost_incl_amortisation
from v_player_contract_costs
group by organisation_id, currency;

-- Latest valuation per player, for squad value.
create view v_latest_valuations as
select distinct on (player_id) player_id, as_of, currency, value, value_low, value_high
from player_valuations
order by player_id, as_of desc;

create view v_squad_value as
select s.organisation_id, v.currency, count(*) as valued_players,
       sum(v.value) as squad_value, sum(v.value_low) as squad_value_low, sum(v.value_high) as squad_value_high
from squad_members s
join v_latest_valuations v on v.player_id = s.player_id
where s.left_on is null
group by s.organisation_id, v.currency;

create view v_budget_vs_actual as
select b.organisation_id, b.fiscal_year, b.category, b.currency, b.amount as budget,
       coalesce(-sum(t.amount), 0) as spent,
       b.amount - coalesce(-sum(t.amount), 0) as remaining
from budgets b
left join financial_transactions t
  on t.organisation_id = b.organisation_id and t.fiscal_year = b.fiscal_year
 and t.category = b.category and t.currency = b.currency
group by b.organisation_id, b.fiscal_year, b.category, b.currency, b.amount;

create view v_revenue_by_stream as
select organisation_id, fiscal_year, currency, category, sum(amount) as revenue
from financial_transactions
where amount > 0
group by organisation_id, fiscal_year, currency, category;

-- Cost per player and output per cost: what a club pays per unit of playing time.
create view v_cost_per_player as
select c.organisation_id, c.player_id, p.full_name, s.role_key, c.currency, c.annual_cost,
       s.exposure, s.exposure_unit,
       case when s.exposure > 0 then round(c.annual_cost / s.exposure, 2) end as cost_per_exposure_unit
from v_player_contract_costs c
join players p on p.id = c.player_id
left join lateral (
  select ps.role_key, ps.exposure, ps.exposure_unit
  from player_season_stats ps join seasons se on se.id = ps.season_id
  where ps.player_id = c.player_id
  order by se.starts_on desc nulls last
  limit 1
) s on true;

commit;
