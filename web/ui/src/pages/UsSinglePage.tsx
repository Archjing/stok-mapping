import { SingleIndexPage } from './SingleIndexPage';
import { US_INDICES } from '../lib/instruments';

/** 美股单标的页。 */
export function UsSinglePage() {
  return (
    <SingleIndexPage
      market="us"
      indices={US_INDICES}
      coreSymbols={US_INDICES.map((i) => i.symbol)}
      initialSymbol="^IXIC"
      initialName="纳斯达克"
    />
  );
}
