/** 前端数据模型（与 scripts/extract.ts 生成的数据结构对应）。 */

export interface IndexBar {
  /** 交易日 YYYY-MM-DD */
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface InstrumentMeta {
  symbol: string;
  name: string;
  kind: 'index' | 'stock';
  start: string;
  end: string;
  count: number;
}

export interface IndexDataFile {
  meta: {
    generatedAt: string;
    source: string;
    instruments: InstrumentMeta[];
  };
  series: Record<string, IndexBar[]>;
}
