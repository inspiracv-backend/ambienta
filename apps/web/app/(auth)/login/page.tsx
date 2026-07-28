import { DevRoleSwitcher, LoginCard } from '@/components/organisms';

export default function LoginPage() {
  return (
    <>
      <LoginCard />
      {/* Herramienta de desarrollo: se elimina del bundle de producción. */}
      <DevRoleSwitcher />
    </>
  );
}
