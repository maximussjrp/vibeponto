'use client';

import { WifiOff, RefreshCcw, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function OfflinePage() {
  const handleRetry = () => {
    window.location.reload();
  };

  const handleGoToPonto = () => {
    // Mesmo offline, pode tentar registrar ponto (será salvo localmente)
    window.location.href = '/dashboard/ponto';
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 flex items-center justify-center p-4">
      <Card className="max-w-md w-full bg-slate-800/50 border-slate-700">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-yellow-500/20 rounded-full flex items-center justify-center mb-4">
            <WifiOff className="w-8 h-8 text-yellow-500" />
          </div>
          <CardTitle className="text-2xl text-white">Você está offline</CardTitle>
          <CardDescription className="text-slate-400">
            Não foi possível conectar à internet. Algumas funcionalidades podem estar limitadas.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-slate-700/50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-2">
              Funcionalidades disponíveis offline:
            </h3>
            <ul className="text-sm text-slate-400 space-y-1">
              <li className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-green-500" />
                Registrar ponto (será sincronizado depois)
              </li>
              <li className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-green-500" />
                Ver dados em cache
              </li>
            </ul>
          </div>
          
          <div className="flex flex-col gap-2">
            <Button 
              onClick={handleGoToPonto} 
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              <Clock className="w-4 h-4 mr-2" />
              Registrar Ponto Offline
            </Button>
            
            <Button 
              onClick={handleRetry} 
              variant="outline" 
              className="w-full border-slate-600 text-slate-300 hover:bg-slate-700"
            >
              <RefreshCcw className="w-4 h-4 mr-2" />
              Tentar Novamente
            </Button>
          </div>
          
          <p className="text-xs text-center text-slate-500">
            Quando a conexão for restaurada, seus dados serão sincronizados automaticamente.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
