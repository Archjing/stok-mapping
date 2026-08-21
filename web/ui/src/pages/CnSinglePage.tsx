import { SingleIndexPage } from './SingleIndexPage';
import { CORE_INDICES, CN_SINGLE_INDICES } from '../lib/instruments';

/** A股单标的页。 */
export function CnSinglePage() {
  return (
    <SingleIndexPage
      market="cn"
      indices={CN_SINGLE_INDICES}
      coreSymbols={CORE_INDICES.map((i) => i.symbol)}
      initialSymbol="SH.000001"
      initialName="上证指数"
      marketLabel="A股"
    />
  );
}
