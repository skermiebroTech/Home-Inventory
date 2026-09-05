/**
 * The routes, and the two gates in front of them.
 *
 * Gate one: the server reports `setup_required` while no account exists. The
 * first visit then goes to the setup wizard.
 * Gate two: a page needs a signed in account, or it sends the visitor to the
 * sign in page.
 */

import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import Layout from '@/components/Layout'
import { Loading } from '@/components/ui'
import { useHealth } from '@/hooks/useSystem'
import { useAuthStore } from '@/store/auth'
import AddItem from '@/pages/AddItem'
import Components from '@/pages/Components'
import Dashboard from '@/pages/Dashboard'
import Export from '@/pages/Export'
import ItemDetailPage from '@/pages/ItemDetail'
import Items from '@/pages/Items'
import Labels from '@/pages/Labels'
import Lending from '@/pages/Lending'
import Locations from '@/pages/Locations'
import Login from '@/pages/Login'
import Maintenance from '@/pages/Maintenance'
import ReceiptDetailPage from '@/pages/ReceiptDetail'
import Receipts from '@/pages/Receipts'
import Settings from '@/pages/Settings'
import Spares from '@/pages/Spares'
import Setup from '@/pages/Setup'
import TagsPage from '@/pages/Tags'

function Protected({ children }: { children: React.ReactNode }) {
  const { accessToken, ready } = useAuthStore()
  const location = useLocation()

  if (!ready) return <Loading label="Checking the session" />
  if (!accessToken) return <Navigate to="/login" replace state={{ from: location }} />
  return <>{children}</>
}

export default function App() {
  const loadUser = useAuthStore((state) => state.loadUser)
  const ready = useAuthStore((state) => state.ready)
  const accessToken = useAuthStore((state) => state.accessToken)
  const health = useHealth()
  const location = useLocation()

  useEffect(() => {
    void loadUser()
  }, [loadUser])

  // The wizard runs while no account exists. A signed in visitor never sees
  // it again, even while the cached health check still says otherwise.
  const setupNeeded = health.data?.setup_required === true && !accessToken
  const onSetup = location.pathname === '/setup'

  if (!ready || health.isLoading) return <Loading label="Starting HomeStock" />
  if (setupNeeded && !onSetup) return <Navigate to="/setup" replace />

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/setup" element={<Setup />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/items" element={<Items />} />
        <Route path="/items/new" element={<AddItem />} />
        <Route path="/items/:id" element={<ItemDetailPage />} />
        <Route path="/locations" element={<Locations />} />
        <Route path="/receipts" element={<Receipts />} />
        <Route path="/receipts/:id" element={<ReceiptDetailPage />} />
        <Route path="/tags" element={<TagsPage />} />
        <Route path="/components" element={<Components />} />
        <Route path="/spares" element={<Spares />} />
        <Route path="/maintenance" element={<Maintenance />} />
        <Route path="/lending" element={<Lending />} />
        <Route path="/labels" element={<Labels />} />
        <Route path="/export" element={<Export />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
