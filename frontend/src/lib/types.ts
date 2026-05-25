// Tipos espelhando os shapes REAIS da API Flask (backend/app/api/*).
// Mantém o frontend honesto: nenhum campo inventado.

export type Role = "coordenador" | "medico";

export type ShiftStatus =
  | "open"
  | "offering"
  | "accepted"
  | "confirmed"
  | "needs_attention"
  | "cancelled";

export type OfferStatus =
  | "pending"
  | "accepted"
  | "declined"
  | "expired"
  | "superseded";

export interface Account {
  id: string;
  email: string;
  role: Role;
  hospital_id: string | null;
}

export interface LoginResponse {
  token: string;
  account: Account;
}

// shift embutido em /me/offers e /me/assignments (subconjunto do shift_view)
export interface EmbeddedShift {
  id: string;
  hospital_id?: string;
  hospital_name?: string;
  specialty_id: number;
  starts_at: string; // ISO 8601 com offset
  ends_at: string;
  rate_cents: number;
  status: ShiftStatus;
}

export interface Offer {
  id: string;
  status: OfferStatus;
  batch_number: number;
  sent_at: string;
  expires_at: string;
  shift: EmbeddedShift;
}

export interface Assignment {
  id: string;
  status: string; // "active" | ...
  accepted_at: string;
  shift: EmbeddedShift;
}

// shift_view completo (services/shifts.py::shift_view)
export interface Shift {
  id: string;
  hospital_id: string;
  specialty_id: number;
  starts_at: string;
  ends_at: string;
  rate_cents: number;
  status: ShiftStatus;
  current_batch: number;
  batch_size: number;
  batch_window_minutes: number;
  escalate_hours_before: number;
  version: number;
  created_at: string | null;
}

export interface AcceptResult {
  shift_id: string;
  offer_id: string;
  status: "accepted";
}

// Oferta detalhada (GET /shifts/:id/offers) — visão da coordenadora
export interface ShiftOfferDoctor {
  id: string;
  name: string;
}

export interface ShiftOfferDetail {
  id: string;
  status: OfferStatus;
  batch_number: number;
  sent_at: string;
  expires_at: string;
  responded_at: string | null;
  doctor: ShiftOfferDoctor;
}

// Médico na listagem (GET /doctors)
export interface DoctorListItem {
  id: string;
  name: string;
  phone: string | null;
  account_id: string | null;
  specialty_ids: number[];
  hospital_ids: string[];
}

// Métricas do médico (GET /doctors/:id/stats)
export interface DoctorStats {
  total_offers: number;
  accepted: number;
  declined: number;
  expired: number;
  acceptance_rate: number | null;
  avg_response_min: number | null;
  total_assignments: number;
}

// Ranking explicável (GET /shifts/:id/ranking) — bônus Tier 1
export interface RankingBreakdown {
  acceptance_rate: number | null; // 0..1
  days_since_last: number | null;
  weekly_load: number;
  avg_response_min: number | null;
  scores: {
    acceptance: number;
    recency: number;
    load: number;
    response: number;
  };
}

export interface ShiftRankingEntry {
  doctor: { id: string; name: string };
  score: number; // 0..100
  already_offered: boolean;
  breakdown: RankingBreakdown;
}

// Indisponibilidade
export interface Unavailability {
  id: string;
  starts_at: string;
  ends_at: string;
  reason: string | null;
}

// Perfil completo do médico (GET /me/profile)
export interface HospitalAffiliation {
  id: string;
  name: string;
  status: "active" | "inactive";
}

export interface DoctorProfile {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  specialty_ids: number[];
  specialties: { id: number; name: string }[];
  hospitals: HospitalAffiliation[];
}

