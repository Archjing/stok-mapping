import { ComparisonDashboard } from '../components/ComparisonDashboard';
import { useTheme } from '../components/ThemeContext';

/** A股对照看板页：直接复用 <ComparisonDashboard>，主题跟随全局。 */
export function CnDashPage() {
  const theme = useTheme();
  return <ComparisonDashboard theme={theme} />;
}
