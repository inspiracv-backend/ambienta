import { Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  const app = await NestFactory.create(AppModule);
  const config = app.get(ConfigService);

  // Todas las rutas de negocio quedan bajo /api/v1; los health checks se
  // excluyen para que orquestadores y balanceadores los consulten en /health
  // sin depender de la versión de la API.
  app.setGlobalPrefix('api/v1', { exclude: ['health', 'health/ready'] });

  app.enableCors({
    origin: config.getOrThrow<string[]>('CORS_ORIGINS'),
    credentials: true,
  });

  // Nota sobre validación de requests: NO se usa el ValidationPipe de NestJS
  // porque depende de class-validator, y este repo ya estandarizó Zod en todas
  // sus capas (packages/shared y config/env.validation.ts). Tener dos sistemas
  // de validación en paralelo sería una fuente de inconsistencias.
  // Cuando se implementen los DTOs (propuesta OpenSpec sistema-actores-roles-rbac),
  // la validación se hará con un ZodValidationPipe sobre los schemas de
  // packages/shared — una sola fuente de verdad de tipos entre web y api.

  // Permite que onModuleDestroy corra al recibir SIGTERM (docker stop),
  // cerrando conexiones a Postgres/Redis en vez de dejarlas colgadas.
  app.enableShutdownHooks();

  // Advertencia visible en cada arranque mientras falten credenciales OAuth —
  // evita que el stub documentado en la propuesta OpenSpec quede olvidado.
  const proveedoresFaltantes = [
    !config.get('MICROSOFT_CLIENT_ID') && 'Microsoft Entra ID',
    !config.get('GOOGLE_CLIENT_ID') && 'Google',
  ].filter(Boolean);
  if (proveedoresFaltantes.length > 0) {
    logger.warn(
      `Login social deshabilitado — sin credenciales de: ${proveedoresFaltantes.join(', ')}. ` +
        'Los endpoints /auth/{proveedor}/callback responderán 501 hasta configurarlas.',
    );
  }

  const port = config.getOrThrow<number>('PORT');
  await app.listen(port, '0.0.0.0');
  logger.log(`API Ambienta escuchando en http://localhost:${port} (${config.get('NODE_ENV')})`);
  logger.log(`Health: http://localhost:${port}/health · Readiness: http://localhost:${port}/health/ready`);
}

bootstrap();
