import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { CnSinglePage } from './pages/CnSinglePage';
import { CnDashPage } from './pages/CnDashPage';
import { UsSinglePage } from './pages/UsSinglePage';

/** 路由：Layout 承载顶栏导航，各功能页作为 Outlet。 */
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'market/cn', element: <CnSinglePage /> },
      { path: 'market/dash', element: <CnDashPage /> },
      { path: 'market/us', element: <UsSinglePage /> },
      // 未知 URL 兜底：重定向回首页
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
