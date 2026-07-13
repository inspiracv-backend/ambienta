export default function Home() {
  return (
    <main style={{ 
      padding: '60px 40px', 
      fontFamily: 'system-ui, -apple-system, sans-serif',
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <h1 style={{ fontSize: '48px', marginBottom: '8px' }}>🌍 Ambienta</h1>
      <p style={{ fontSize: '20px', color: '#555', marginBottom: '40px' }}>
        Sistema de cumplimiento ambiental para empresas industriales
      </p>

      <div style={{ 
        background: '#f8f9fa', 
        padding: '24px', 
        borderRadius: '12px',
        marginBottom: '30px'
      }}>
        <h2 style={{ marginTop: 0 }}>Estado del proyecto</h2>
        <p><strong>✅ Semana 3 - Lunes completado</strong></p>
        <ul>
          <li>Monorepo Turborepo levantado</li>
          <li>Frontend Next.js funcionando</li>
          <li>Backend NestJS funcionando</li>
          <li>CLAUDE.md y estructura lista</li>
        </ul>
      </div>

      <p style={{ color: '#666', fontSize: '14px' }}>
        Backend API: <a href="http://localhost:3001" target="_blank">http://localhost:3001</a>
      </p>
    </main>
  );
}