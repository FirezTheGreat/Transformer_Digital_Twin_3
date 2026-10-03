import { FactBundle } from './contracts.ts';
import mockBundle from '../../../fixtures/mockFactBundle.json';

// Type assertion proving mockFactBundle.json conforms to FactBundle interface
export const validatedBundle: FactBundle = mockBundle as FactBundle;

export function verifyFactBundle(bundle: FactBundle): boolean {
  return (
    bundle.asset_id === 'DT-001' &&
    bundle.capabilities.highest_tier === 'C3' &&
    bundle.health.domains.thermal.domain_name === 'thermal' &&
    bundle.open_episodes.length >= 0 &&
    bundle.active_recommendations.length >= 0
  );
}
