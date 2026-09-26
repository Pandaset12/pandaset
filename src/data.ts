export type Asset = {
  symbol: string;
  name: string;
  short: string;
  sector: string;
  color: string;
  price: number;
  target: number;
  vol: number;
  beta: number;
  description: string;
  thesis: string;
  watch: string;
  source: string;
};
export const assets: Asset[] = [
  {
    symbol: "NVDA",
    name: "NVIDIA Corporation",
    short: "NVIDIA",
    sector: "Technology",
    color: "#c2a36b",
    price: 142.87,
    target: 0.428,
    vol: 0.39,
    beta: 1.72,
    description:
      "Accelerated computing, data-center infrastructure, and graphics processors.",
    thesis:
      "Demand for accelerated computing connects NVIDIA to the expansion of AI infrastructure.",
    watch:
      "Customer concentration, export restrictions, and the pace of infrastructure spending.",
    source:
      "https://investor.nvidia.com/financial-info/financial-reports-and-sec-filings/default.aspx",
  },
  {
    symbol: "MSFT",
    name: "Microsoft Corporation",
    short: "Microsoft",
    sector: "Technology",
    color: "#7fa487",
    price: 468.35,
    target: 0.221,
    vol: 0.23,
    beta: 1.07,
    description:
      "Enterprise software, cloud infrastructure, and productivity applications.",
    thesis:
      "Recurring enterprise subscriptions and cloud services diversify its revenue mix.",
    watch:
      "Cloud margins, infrastructure investment, and adoption of paid AI products.",
    source:
      "https://www.microsoft.com/en-us/Investor/earnings/FY-2025-Q4/press-release-webcast",
  },
  {
    symbol: "AAPL",
    name: "Apple Inc.",
    short: "Apple",
    sector: "Technology",
    color: "#d07d72",
    price: 231.62,
    target: 0.126,
    vol: 0.26,
    beta: 1.16,
    description:
      "Consumer devices, software, and services built around a connected ecosystem.",
    thesis:
      "A large installed device base supports recurring services revenue.",
    watch:
      "Device replacement cycles, regional demand, and regulatory changes.",
    source: "https://investor.apple.com/sec-filings/default.aspx",
  },
  {
    symbol: "JPM",
    name: "JPMorgan Chase & Co.",
    short: "JPMorgan Chase",
    sector: "Financials",
    color: "#ad8f73",
    price: 291.14,
    target: 0.184,
    vol: 0.22,
    beta: 1.03,
    description:
      "Consumer banking, investment banking, asset management, and payments.",
    thesis:
      "A diversified banking franchise adds a different earnings driver to a technology-heavy portfolio.",
    watch: "Credit quality, interest-rate sensitivity, and lending demand.",
    source: "https://www.jpmorganchase.com/ir/annual-report",
  },
  {
    symbol: "VTI",
    name: "Vanguard Total Stock Market ETF",
    short: "Vanguard Total Market",
    sector: "Broad market",
    color: "#9aa97c",
    price: 312.46,
    target: 0.152,
    vol: 0.17,
    beta: 1,
    description:
      "Broad exposure to the U.S. equity market across large, mid, and small companies.",
    thesis:
      "Broad market exposure spreads capital across many companies and industries.",
    watch:
      "Market-wide drawdowns and overlap with directly held large technology companies.",
    source:
      "https://investor.vanguard.com/investment-products/etfs/profile/vti",
  },
  {
    symbol: "TLT",
    name: "iShares 20+ Year Treasury Bond ETF",
    short: "iShares Treasury Bond",
    sector: "Treasuries",
    color: "#b67e78",
    price: 88.73,
    target: -0.038,
    vol: 0.18,
    beta: -0.18,
    description:
      "Exposure to U.S. Treasury bonds with remaining maturities greater than twenty years.",
    thesis:
      "Long-duration Treasury exposure introduces a different source of returns from equities.",
    watch:
      "Sensitivity to long-term interest rates; bonds and equities can decline together.",
    source:
      "https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf",
  },
  {
    symbol: "AMD",
    name: "Advanced Micro Devices, Inc.",
    short: "AMD",
    sector: "Technology",
    color: "#d99e5c",
    price: 164.28,
    target: 0.243,
    vol: 0.43,
    beta: 1.65,
    description:
      "Processors and accelerated computing products for data centers and personal devices.",
    thesis:
      "Data-center and client computing offer several routes to revenue growth.",
    watch:
      "Semiconductor competition, execution, and cyclical customer demand.",
    source: "https://ir.amd.com/financial-information/sec-filings",
  },
  {
    symbol: "GLD",
    name: "SPDR Gold Shares",
    short: "SPDR Gold",
    sector: "Gold",
    color: "#dcc58e",
    price: 284.59,
    target: 0.148,
    vol: 0.16,
    beta: 0.08,
    description:
      "An exchange-traded fund designed to track the price of gold bullion, less expenses.",
    thesis:
      "Gold exposure introduces a return driver beyond corporate earnings.",
    watch:
      "Real interest rates, the U.S. dollar, and the absence of cash distributions.",
    source: "https://www.spdrgoldshares.com/usa/",
  },
];
export const initialWeights = [24, 20, 16, 12, 18, 10, 0, 0];
export const portfolioValue = 128450;
export const asOf = "Sep 25, 2026";
export const assetBySymbol = (symbol: string) =>
  assets.find((a) => a.symbol === symbol) ?? assets[0];
// Deterministic illustrative observations. They are not a historical market feed.
let rngState = 73019;
function random() {
  rngState = (Math.imul(1664525, rngState) + 1013904223) >>> 0;
  return (rngState + 1) / 4294967297;
}
function normal() {
  return Math.sqrt(-2 * Math.log(random())) * Math.cos(2 * Math.PI * random());
}
const count = 252;
const factors = Array.from({ length: count }, () => [
  normal(),
  normal(),
  normal(),
]);
export const returns = assets.map((asset, idx) => {
  const raw = factors.map(([market, tech, rate]) => {
    const exposure =
      idx === 5 ? -0.12 : idx === 7 ? 0.08 : idx === 4 ? 0.94 : 0.65;
    const technology = asset.sector === "Technology" ? 0.48 : 0;
    const rates = idx === 5 ? 0.83 : idx === 7 ? 0.42 : 0.08;
    const remaining = Math.sqrt(
      Math.max(0.02, 1 - exposure ** 2 - technology ** 2 - rates ** 2),
    );
    return (
      (asset.vol / Math.sqrt(252)) *
      (market * exposure +
        tech * technology +
        rate * rates +
        normal() * remaining)
    );
  });
  const drift =
    (Math.log(1 + asset.target) - raw.reduce((a, b) => a + b, 0)) / count;
  return raw.map((r) => Math.exp(r + drift) - 1);
});
const dates: string[] = [];
const end = new Date("2026-09-25T12:00:00Z");
while (dates.length < 253) {
  if (end.getUTCDay() !== 0 && end.getUTCDay() !== 6)
    dates.unshift(end.toISOString().slice(0, 10));
  end.setUTCDate(end.getUTCDate() - 1);
}
export { dates };
export const researchNotes = [
  {
    id: "compute",
    category: "EARNINGS & STRATEGY",
    title: "The AI infrastructure thread",
    body: "NVIDIA and Microsoft share exposure to AI infrastructure spending. Their business models differ, but a common demand driver can connect their returns.",
    symbols: ["NVDA", "MSFT", "AMD"],
    source: "NVIDIA investor relations",
    url: assets[0].source,
    read: "Research primer",
  },
  {
    id: "rates",
    category: "MACRO & EXPOSURE",
    title: "One rate move. Different effects.",
    body: "Changes in long-term yields can affect Treasury prices, bank earnings, and equity valuations in different ways. Review your combined exposure before treating bonds as a complete hedge.",
    symbols: ["TLT", "JPM"],
    source: "Federal Reserve",
    url: "https://www.federalreserve.gov/monetarypolicy.htm",
    read: "Research primer",
  },
  {
    id: "overlap",
    category: "PORTFOLIO STRUCTURE",
    title: "A broad fund can still overlap",
    body: "A total-market ETF may hold companies you also own directly. Fund ownership and direct ownership should be considered together when assessing concentration.",
    symbols: ["VTI", "AAPL", "MSFT", "NVDA"],
    source: "Vanguard fund profile",
    url: assets[4].source,
    read: "Research primer",
  },
  {
    id: "consumer",
    category: "BUSINESS FUNDAMENTALS",
    title: "Looking beyond the device cycle",
    body: "Apple combines hardware demand with recurring services. Researching both helps distinguish a product-cycle change from a broader shift in the business.",
    symbols: ["AAPL"],
    source: "Apple investor relations",
    url: assets[2].source,
    read: "Research primer",
  },
];
