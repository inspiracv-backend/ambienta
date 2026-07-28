import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { validateEnv } from './config/env.validation';
import { HealthModule } from './health/health.module';

/**
 * Módulo raíz de la API.
 *
 * Hoy solo contiene infraestructura (configuración validada + health checks).
 * Los módulos de negocio (auth, tenants, usuarios, permisos, audit log) se
 * agregan cuando se apruebe la propuesta
 * `openspec/changes/sistema-actores-roles-rbac/` — regla no negociable de
 * CLAUDE.md: solo se implementan features con spec aprobada.
 */
@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      // Sin `envFilePath`: en Docker las variables llegan por el entorno del
      // contenedor (env_file / secrets), no por un .env dentro de la imagen.
      validate: validateEnv,
    }),
    HealthModule,
  ],
})
export class AppModule {}
