import { Controller, Get, HttpStatus, Res } from '@nestjs/common';
import type { Response } from 'express';
import { HealthService } from './health.service';

@Controller('health')
export class HealthController {
  constructor(private readonly health: HealthService) {}

  /**
   * Liveness probe: ¿el proceso está vivo? No consulta dependencias a propósito —
   * si Postgres se cae, el contenedor NO debe reiniciarse (reiniciarlo no arregla
   * la base de datos); para eso está el readiness probe.
   */
  @Get()
  liveness() {
    return {
      estado: 'ok',
      servicio: 'ambienta-api',
      timestamp: new Date().toISOString(),
      uptimeSegundos: Math.floor(process.uptime()),
    };
  }

  /**
   * Readiness probe: ¿puede la API atender tráfico? Verifica Postgres y Redis.
   * Devuelve 503 si alguna dependencia falla, para que el balanceador la saque
   * de rotación sin matar el contenedor.
   */
  @Get('ready')
  async readiness(@Res() res: Response) {
    const resultado = await this.health.verificarReadiness();
    const codigo = resultado.estado === 'ok' ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE;
    return res.status(codigo).json({ ...resultado, timestamp: new Date().toISOString() });
  }
}
