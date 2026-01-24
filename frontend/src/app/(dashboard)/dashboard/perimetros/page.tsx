'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { 
  Map, 
  MapPin, 
  Trash2, 
  Save, 
  Undo, 
  Redo, 
  Circle,
  Pentagon,
  Crosshair,
  Layers,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Check,
  X,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import toast from 'react-hot-toast';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface Coordinate {
  lat: number;
  lng: number;
}

interface Perimetro {
  id?: string;
  nome: string;
  descricao: string;
  tipo: 'circulo' | 'poligono';
  centro: Coordinate;
  raio_metros?: number;
  coordenadas?: Coordinate[];
  tolerancia_metros: number;
  tolerancia_minutos: number;
  ativo: boolean;
  equipe_id?: string;
  cor?: string;
}

type DrawingMode = 'none' | 'circle' | 'polygon' | 'marker';

// Componente do mapa usando canvas (sem dependência externa)
function MapCanvas({
  perimetros,
  currentPerimetro,
  drawingMode,
  onPointClick,
  onCenterChange,
  center,
  zoom,
}: {
  perimetros: Perimetro[];
  currentPerimetro: Partial<Perimetro> | null;
  drawingMode: DrawingMode;
  onPointClick: (coord: Coordinate) => void;
  onCenterChange: (coord: Coordinate) => void;
  center: Coordinate;
  zoom: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  // Converter coordenadas geográficas para pixels
  const latLngToPixel = useCallback((coord: Coordinate): { x: number; y: number } => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const scale = Math.pow(2, zoom) * 256 / 360;
    const x = (coord.lng - center.lng) * scale + canvas.width / 2 + offset.x;
    
    const latRad = (coord.lat * Math.PI) / 180;
    const centerLatRad = (center.lat * Math.PI) / 180;
    const y = canvas.height / 2 - 
      (Math.log(Math.tan(Math.PI / 4 + latRad / 2)) - 
       Math.log(Math.tan(Math.PI / 4 + centerLatRad / 2))) * 
      scale * 180 / Math.PI + offset.y;

    return { x, y };
  }, [center, zoom, offset]);

  // Converter pixels para coordenadas geográficas
  const pixelToLatLng = useCallback((x: number, y: number): Coordinate => {
    const canvas = canvasRef.current;
    if (!canvas) return { lat: 0, lng: 0 };

    const scale = Math.pow(2, zoom) * 256 / 360;
    const lng = (x - canvas.width / 2 - offset.x) / scale + center.lng;
    
    const yOffset = (y - canvas.height / 2 - offset.y) / scale;
    const centerLatRad = (center.lat * Math.PI) / 180;
    const latRad = 2 * Math.atan(Math.exp(
      Math.log(Math.tan(Math.PI / 4 + centerLatRad / 2)) - 
      yOffset * Math.PI / 180
    )) - Math.PI / 2;
    const lat = (latRad * 180) / Math.PI;

    return { lat, lng };
  }, [center, zoom, offset]);

  // Desenhar mapa
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    // Limpar canvas
    ctx.fillStyle = '#e5e7eb';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Grid
    ctx.strokeStyle = '#d1d5db';
    ctx.lineWidth = 1;
    for (let i = 0; i < canvas.width; i += 50) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, canvas.height);
      ctx.stroke();
    }
    for (let i = 0; i < canvas.height; i += 50) {
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(canvas.width, i);
      ctx.stroke();
    }

    // Desenhar perímetros existentes
    perimetros.forEach((p) => {
      const cor = p.cor || '#3b82f6';
      ctx.strokeStyle = cor;
      ctx.fillStyle = cor + '40';
      ctx.lineWidth = 2;

      if (p.tipo === 'circulo' && p.centro && p.raio_metros) {
        const centerPixel = latLngToPixel(p.centro);
        const edgeCoord = {
          lat: p.centro.lat,
          lng: p.centro.lng + p.raio_metros / 111320,
        };
        const edgePixel = latLngToPixel(edgeCoord);
        const radiusPixels = Math.abs(edgePixel.x - centerPixel.x);

        ctx.beginPath();
        ctx.arc(centerPixel.x, centerPixel.y, radiusPixels, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Label
        ctx.fillStyle = '#1f2937';
        ctx.font = '12px sans-serif';
        ctx.fillText(p.nome, centerPixel.x - 20, centerPixel.y);
      }

      if (p.tipo === 'poligono' && p.coordenadas && p.coordenadas.length > 2) {
        ctx.beginPath();
        const firstPoint = latLngToPixel(p.coordenadas[0]);
        ctx.moveTo(firstPoint.x, firstPoint.y);
        
        p.coordenadas.slice(1).forEach((coord) => {
          const point = latLngToPixel(coord);
          ctx.lineTo(point.x, point.y);
        });
        
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Label no centro
        if (p.centro) {
          const centerPixel = latLngToPixel(p.centro);
          ctx.fillStyle = '#1f2937';
          ctx.font = '12px sans-serif';
          ctx.fillText(p.nome, centerPixel.x - 20, centerPixel.y);
        }
      }
    });

    // Desenhar perímetro em edição
    if (currentPerimetro) {
      ctx.strokeStyle = '#ef4444';
      ctx.fillStyle = '#ef444440';
      ctx.lineWidth = 3;

      if (currentPerimetro.tipo === 'circulo' && currentPerimetro.centro) {
        const centerPixel = latLngToPixel(currentPerimetro.centro);
        const raio = currentPerimetro.raio_metros || 50;
        const edgeCoord = {
          lat: currentPerimetro.centro.lat,
          lng: currentPerimetro.centro.lng + raio / 111320,
        };
        const edgePixel = latLngToPixel(edgeCoord);
        const radiusPixels = Math.abs(edgePixel.x - centerPixel.x);

        ctx.beginPath();
        ctx.arc(centerPixel.x, centerPixel.y, radiusPixels, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Marcador do centro
        ctx.fillStyle = '#ef4444';
        ctx.beginPath();
        ctx.arc(centerPixel.x, centerPixel.y, 6, 0, Math.PI * 2);
        ctx.fill();
      }

      if (currentPerimetro.tipo === 'poligono' && currentPerimetro.coordenadas) {
        const coords = currentPerimetro.coordenadas;
        
        if (coords.length > 0) {
          ctx.beginPath();
          const firstPoint = latLngToPixel(coords[0]);
          ctx.moveTo(firstPoint.x, firstPoint.y);
          
          coords.slice(1).forEach((coord) => {
            const point = latLngToPixel(coord);
            ctx.lineTo(point.x, point.y);
          });
          
          if (coords.length > 2) {
            ctx.closePath();
            ctx.fill();
          }
          ctx.stroke();

          // Pontos do polígono
          coords.forEach((coord, i) => {
            const point = latLngToPixel(coord);
            ctx.fillStyle = i === 0 ? '#22c55e' : '#ef4444';
            ctx.beginPath();
            ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
          });
        }
      }
    }

    // Crosshair no centro
    ctx.strokeStyle = '#6b7280';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(canvas.width / 2, 0);
    ctx.lineTo(canvas.width / 2, canvas.height);
    ctx.moveTo(0, canvas.height / 2);
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.stroke();
    ctx.setLineDash([]);

  }, [perimetros, currentPerimetro, latLngToPixel]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resizeObserver = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      draw();
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, [draw]);

  // Redesenhar quando mudar dependências
  useEffect(() => {
    draw();
  }, [draw]);

  // Handlers de mouse
  const handleMouseDown = (e: React.MouseEvent) => {
    if (drawingMode === 'none') {
      setIsDragging(true);
      setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleClick = (e: React.MouseEvent) => {
    if (drawingMode !== 'none') {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;

      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const coord = pixelToLatLng(x, y);
      onPointClick(coord);
    }
  };

  return (
    <div 
      ref={containerRef} 
      className="w-full h-full min-h-[400px] relative cursor-crosshair"
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleClick}
        className="w-full h-full"
        style={{ cursor: isDragging ? 'grabbing' : drawingMode !== 'none' ? 'crosshair' : 'grab' }}
      />
      
      {/* Info overlay */}
      <div className="absolute bottom-2 left-2 bg-white/90 dark:bg-slate-800/90 rounded px-2 py-1 text-xs">
        Lat: {center.lat.toFixed(6)}, Lng: {center.lng.toFixed(6)} | Zoom: {zoom}
      </div>
    </div>
  );
}

export default function PerimetrosMapaPage() {
  const queryClient = useQueryClient();
  
  // Estados
  const [drawingMode, setDrawingMode] = useState<DrawingMode>('none');
  const [center, setCenter] = useState<Coordinate>({ lat: -23.5505, lng: -46.6333 });
  const [zoom, setZoom] = useState(15);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [currentPerimetro, setCurrentPerimetro] = useState<Partial<Perimetro> | null>(null);
  const [polygonPoints, setPolygonPoints] = useState<Coordinate[]>([]);

  // Formulário
  const [formData, setFormData] = useState({
    nome: '',
    descricao: '',
    tolerancia_metros: 50,
    tolerancia_minutos: 5,
    ativo: true,
    cor: '#3b82f6',
  });

  // Buscar perímetros existentes
  const { data: perimetros = [], isLoading } = useQuery({
    queryKey: ['perimetros'],
    queryFn: async () => {
      const response = await api.get('/geo/perimetros');
      return response.data.items as Perimetro[];
    },
  });

  // Mutation para salvar
  const saveMutation = useMutation({
    mutationFn: async (data: Partial<Perimetro>) => {
      if (data.id) {
        return api.put(`/geo/perimetros/${data.id}`, data);
      }
      return api.post('/geo/perimetros', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['perimetros'] });
      toast.success('Perímetro salvo com sucesso!');
      handleCancel();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Erro ao salvar perímetro');
    },
  });

  // Mutation para deletar
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.delete(`/geo/perimetros/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['perimetros'] });
      toast.success('Perímetro removido!');
    },
  });

  // Obter localização atual
  const handleGetLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setCenter({
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          });
          toast.success('Localização obtida!');
        },
        (error) => {
          toast.error('Erro ao obter localização');
        }
      );
    }
  };

  // Iniciar desenho de círculo
  const handleStartCircle = () => {
    setDrawingMode('circle');
    setCurrentPerimetro({
      tipo: 'circulo',
      raio_metros: 100,
    });
    setPolygonPoints([]);
    toast.info('Clique no mapa para definir o centro do círculo');
  };

  // Iniciar desenho de polígono
  const handleStartPolygon = () => {
    setDrawingMode('polygon');
    setCurrentPerimetro({
      tipo: 'poligono',
      coordenadas: [],
    });
    setPolygonPoints([]);
    toast.info('Clique no mapa para adicionar pontos. Clique no primeiro ponto para fechar.');
  };

  // Handler de clique no mapa
  const handlePointClick = (coord: Coordinate) => {
    if (drawingMode === 'circle') {
      setCurrentPerimetro(prev => ({
        ...prev,
        centro: coord,
      }));
      setIsDialogOpen(true);
    } else if (drawingMode === 'polygon') {
      const newPoints = [...polygonPoints, coord];
      setPolygonPoints(newPoints);
      
      // Calcular centro
      const centroLat = newPoints.reduce((sum, p) => sum + p.lat, 0) / newPoints.length;
      const centroLng = newPoints.reduce((sum, p) => sum + p.lng, 0) / newPoints.length;
      
      setCurrentPerimetro(prev => ({
        ...prev,
        coordenadas: newPoints,
        centro: { lat: centroLat, lng: centroLng },
      }));

      if (newPoints.length >= 3) {
        // Verificar se clicou próximo ao primeiro ponto
        const firstPoint = newPoints[0];
        const distance = Math.sqrt(
          Math.pow(coord.lat - firstPoint.lat, 2) + 
          Math.pow(coord.lng - firstPoint.lng, 2)
        );
        
        if (distance < 0.0001 && newPoints.length > 3) {
          // Fechar polígono
          setIsDialogOpen(true);
        }
      }
    }
  };

  // Finalizar desenho
  const handleFinishDrawing = () => {
    if (drawingMode === 'polygon' && polygonPoints.length >= 3) {
      setIsDialogOpen(true);
    }
  };

  // Cancelar
  const handleCancel = () => {
    setDrawingMode('none');
    setCurrentPerimetro(null);
    setPolygonPoints([]);
    setIsDialogOpen(false);
    setFormData({
      nome: '',
      descricao: '',
      tolerancia_metros: 50,
      tolerancia_minutos: 5,
      ativo: true,
      cor: '#3b82f6',
    });
  };

  // Salvar perímetro
  const handleSave = () => {
    if (!formData.nome) {
      toast.error('Digite um nome para o perímetro');
      return;
    }

    const data: Partial<Perimetro> = {
      ...currentPerimetro,
      ...formData,
    };

    saveMutation.mutate(data);
  };

  // Desfazer último ponto
  const handleUndo = () => {
    if (polygonPoints.length > 0) {
      const newPoints = polygonPoints.slice(0, -1);
      setPolygonPoints(newPoints);
      setCurrentPerimetro(prev => ({
        ...prev,
        coordenadas: newPoints,
      }));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Perímetros de Geofencing</h1>
          <p className="text-slate-500">
            Desenhe áreas permitidas para registro de ponto
          </p>
        </div>
        <Badge variant="outline">
          {perimetros.length} perímetros
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Painel de controle */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Ferramentas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Modo de desenho */}
            <div className="space-y-2">
              <Label>Desenhar</Label>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant={drawingMode === 'circle' ? 'default' : 'outline'}
                  size="sm"
                  onClick={handleStartCircle}
                  className="gap-2"
                >
                  <Circle className="h-4 w-4" />
                  Círculo
                </Button>
                <Button
                  variant={drawingMode === 'polygon' ? 'default' : 'outline'}
                  size="sm"
                  onClick={handleStartPolygon}
                  className="gap-2"
                >
                  <Pentagon className="h-4 w-4" />
                  Polígono
                </Button>
              </div>
            </div>

            {/* Ações de desenho */}
            {drawingMode !== 'none' && (
              <div className="space-y-2">
                <Label>Ações</Label>
                <div className="flex gap-2">
                  {drawingMode === 'polygon' && polygonPoints.length > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleUndo}
                    >
                      <Undo className="h-4 w-4" />
                    </Button>
                  )}
                  {drawingMode === 'polygon' && polygonPoints.length >= 3 && (
                    <Button
                      variant="default"
                      size="sm"
                      onClick={handleFinishDrawing}
                      className="gap-1"
                    >
                      <Check className="h-4 w-4" />
                      Finalizar
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCancel}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                {drawingMode === 'polygon' && (
                  <p className="text-xs text-slate-500">
                    {polygonPoints.length} pontos adicionados
                  </p>
                )}
              </div>
            )}

            {/* Navegação */}
            <div className="space-y-2">
              <Label>Navegação</Label>
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-2"
                onClick={handleGetLocation}
              >
                <Crosshair className="h-4 w-4" />
                Minha Localização
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoom(z => Math.min(z + 1, 20))}
                >
                  <ZoomIn className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoom(z => Math.max(z - 1, 10))}
                >
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCenter({ lat: -23.5505, lng: -46.6333 })}
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Lista de perímetros */}
            <div className="space-y-2">
              <Label>Perímetros Salvos</Label>
              {isLoading ? (
                <div className="flex justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              ) : perimetros.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-2">
                  Nenhum perímetro cadastrado
                </p>
              ) : (
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {perimetros.map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between p-2 rounded border hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: p.cor || '#3b82f6' }}
                        />
                        <span className="text-sm truncate max-w-[100px]">
                          {p.nome}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (confirm('Remover perímetro?')) {
                            deleteMutation.mutate(p.id!);
                          }
                        }}
                      >
                        <Trash2 className="h-3 w-3 text-red-500" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Mapa */}
        <Card className="lg:col-span-3">
          <CardContent className="p-0 overflow-hidden rounded-lg">
            <div className="h-[500px]">
              <MapCanvas
                perimetros={perimetros}
                currentPerimetro={currentPerimetro}
                drawingMode={drawingMode}
                onPointClick={handlePointClick}
                onCenterChange={setCenter}
                center={center}
                zoom={zoom}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Dialog de configuração */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configurar Perímetro</DialogTitle>
            <DialogDescription>
              Defina as propriedades da área de geofencing
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Nome</Label>
              <Input
                value={formData.nome}
                onChange={(e) => setFormData(prev => ({ ...prev, nome: e.target.value }))}
                placeholder="Ex: Sede Principal"
              />
            </div>

            <div className="space-y-2">
              <Label>Descrição</Label>
              <Textarea
                value={formData.descricao}
                onChange={(e) => setFormData(prev => ({ ...prev, descricao: e.target.value }))}
                placeholder="Descrição opcional"
                rows={2}
              />
            </div>

            {currentPerimetro?.tipo === 'circulo' && (
              <div className="space-y-2">
                <Label>Raio (metros)</Label>
                <Input
                  type="number"
                  value={currentPerimetro.raio_metros || 100}
                  onChange={(e) => 
                    setCurrentPerimetro(prev => ({ ...prev, raio_metros: parseInt(e.target.value) || 100 }))
                  }
                  min={10}
                  max={1000}
                  step={10}
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Tolerância (metros)</Label>
                <Input
                  type="number"
                  value={formData.tolerancia_metros}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    tolerancia_metros: parseInt(e.target.value) || 0 
                  }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Tolerância (minutos)</Label>
                <Input
                  type="number"
                  value={formData.tolerancia_minutos}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    tolerancia_minutos: parseInt(e.target.value) || 0 
                  }))}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Cor</Label>
              <div className="flex gap-2">
                {['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6'].map((color) => (
                  <button
                    key={color}
                    className={`w-8 h-8 rounded-full border-2 ${
                      formData.cor === color ? 'border-slate-900' : 'border-transparent'
                    }`}
                    style={{ backgroundColor: color }}
                    onClick={() => setFormData(prev => ({ ...prev, cor: color }))}
                  />
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <Label>Ativo</Label>
              <Switch
                checked={formData.ativo}
                onCheckedChange={(checked) => 
                  setFormData(prev => ({ ...prev, ativo: checked }))
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={handleCancel}>
              Cancelar
            </Button>
            <Button 
              onClick={handleSave}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
