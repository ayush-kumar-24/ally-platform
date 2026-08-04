/**
 * services/reference.js — static-ish lookup data owned by the backend.
 *
 * Stages, industries and business pillars drive dropdowns and the diagnosis
 * dimension labels. They live server-side so the options a founder picks from are
 * always the ones the diagnosis engine actually recognises — a hardcoded frontend
 * list drifts the moment the taxonomy changes.
 */

import { get } from './api';

export function getStages() {
  return get('/reference/stages');
}

export function getIndustries() {
  return get('/reference/industries');
}

export function getBusinessPillars() {
  return get('/reference/business-pillars');
}
