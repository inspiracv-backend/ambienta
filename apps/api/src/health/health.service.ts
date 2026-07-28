import { Injectable, Logger, type OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool } from 'pg';
import Redis from 'ioredis';

export type EstadoDependencia = 'ok' | 'error';

export interface ChequeoDependencia {
  estado: EstadoDependencia;
  latenciaMs?: number;
  error?: string;
}

export interface ResultadoReadiness {
  estado: EstadoDependencia;
  dependencias: {
    postgres: ChequeoDependencia;
    redis: ChequeoDependencia;
  };
}

/**
 * Chequeos de infraestructura para el readiness probe.
 *
 * IMPORTANTE: estos clientes existen SOLO para verificar conectividad — no son
 * la capa de datos de la aplicación. El ORM, el esquema y las políticas RLS se
 * definen en la propuesta OpenSpec `sistema-actores-roles-rbac` (pendiente de
 * aprobación); no se debe construir lógica de negocio sobre este pool.
 */
@Injectable()
export class HealthService implements OnModuleDestroy {
  private readonly logger = new Logger(HealthService.name);
  private readonly pool: Pool;
  private readonly redis: Redis;

  constructor(config: ConfigService) {
    this.pool = new Pool({
      connectionString: config.getOrThrow<string>('DATABASE_URL'),
      max: 2,
      connectionTimeoutMillis: 3000,
    });

    this.redis = new Redis(config.getOrThrow<string>('REDIS_URL'), {
      maxRetriesPerRequest: 1,
      connectTimeout: 3000,
      lazyConnect: true,
      // Evita que ioredis reintente indefinidamente y llene los logs cuando
      // Redis está caído — el readiness probe debe fallar rápido, no colgarse.
      retryStrategy: () => null,
    });
    // Sin este handler, un fallo de conexión de ioredis emite un 'error' no
    // capturado que tumba el proceso entero en vez de degradar el readiness.
    this.redis.on('error', (error) => {
      this.logger.warn(`Redis no disponible: ${error.message}`);
    });
  }

  async verificarReadiness(): Promise<ResultadoReadiness> {
    const [postgres, redis] = await Promise.all([this.verificarPostgres(), this.verificarRedis()]);
    const estado: EstadoDependencia =
      postgres.estado === 'ok' && redis.estado === 'ok' ? 'ok' : 'error';

    return { estado, dependencias: { postgres, redis } };
  }

  private async verificarPostgres(): Promise<ChequeoDependencia> {
    const inicio = Date.now();
    try {
      await this.pool.query('SELECT 1');
      return { estado: 'ok', latenciaMs: Date.now() - inicio };
    } catch (error) {
      return { estado: 'error', error: (error as Error).message };
    }
  }

  private async verificarRedis(): Promise<ChequeoDependencia> {
    const inicio = Date.now();
    try {
      if (this.redis.status !== 'ready') await this.redis.connect();
      await this.redis.ping();
      return { estado: 'ok', latenciaMs: Date.now() - inicio };
    } catch (error) {
      return { estado: 'error', error: (error as Error).message };
    }
  }

  /** Cierra las conexiones al apagar el proceso (evita conexiones colgadas en Postgres). */
  async onModuleDestroy(): Promise<void> {
    await Promise.allSettled([this.pool.end(), this.redis.quit()]);
  }
}
