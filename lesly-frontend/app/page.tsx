import PremiumDashboard from '../components/PremiumDashboard';
import AuthGate from '../components/AuthGate';

export default function Home() {
  return (
    <AuthGate>
      <PremiumDashboard />
    </AuthGate>
  );
}
