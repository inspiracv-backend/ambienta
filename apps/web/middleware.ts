import { NextResponse, type NextRequest } from 'next/server';
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { CLERK_HABILITADO } from '@/lib/clerk-config';

/**
 * Rutas que se ven sin sesión: el propio login, el registro, y el acceso de
 * cliente invitado, que por diseño no exige cuenta (RF-02).
 */
const esPublica = createRouteMatcher([
  '/login(.*)',
  '/signup(.*)',
  '/acceso-invitado(.*)',
  '/crear-ticket(.*)',
]);

const conClerk = clerkMiddleware(async (auth, req) => {
  if (esPublica(req)) return;

  // `unauthenticatedUrl` explicito. Sin el, `auth.protect()` manda al Account
  // Portal alojado de Clerk (`<slug>.accounts.dev/sign-in`), que en desarrollo
  // el navegador bloquea por cambio de origen y deja un bucle de redirecciones
  // entre el portal y /dashboard. Nuestro login es una pantalla nuestra.
  await auth.protect({
    unauthenticatedUrl: new URL('/login', req.url).toString(),
  });
});

/**
 * Sin proveedor configurado el middleware deja pasar todo.
 *
 * `clerkMiddleware()` sin llave falla igual que el provider, así que no se
 * puede llamar incondicionalmente. Y no hay nada que proteger: sin proveedor
 * no existe sesión que verificar. Las pantallas siguen cubiertas por los
 * guards del cliente, que es exactamente como funcionaba antes de este cambio.
 */
export default function middleware(req: NextRequest, evento: any) {
  if (!CLERK_HABILITADO) return NextResponse.next();
  return conClerk(req, evento);
}

export const config = {
  // Todo menos los estáticos de Next y los archivos con extensión. El webhook
  // de Clerk vive en la API (FastAPI), no acá, así que no hay que excluirlo.
  matcher: ['/((?!_next|[^?]*\\.(?:html?|css|js|jpe?g|png|gif|svg|ico|webp|woff2?)).*)'],
};
