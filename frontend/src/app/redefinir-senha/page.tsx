"use client";

import { Suspense, useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { api, getErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Clock, 
  Lock, 
  ArrowLeft, 
  Loader2,
  CheckCircle,
  Eye,
  EyeOff,
  XCircle,
} from "lucide-react";

const senhaSchema = z.object({
  nova_senha: z.string()
    .min(8, "A senha deve ter pelo menos 8 caracteres")
    .regex(/[A-Z]/, "A senha deve conter pelo menos uma letra maiúscula")
    .regex(/[a-z]/, "A senha deve conter pelo menos uma letra minúscula")
    .regex(/[0-9]/, "A senha deve conter pelo menos um número"),
  confirmar_senha: z.string(),
}).refine((data) => data.nova_senha === data.confirmar_senha, {
  message: "As senhas não coincidem",
  path: ["confirmar_senha"],
});

type SenhaForm = z.infer<typeof senhaSchema>;

function RedefinirSenhaContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isValidToken, setIsValidToken] = useState<boolean | null>(null);
  const [showNovaSenha, setShowNovaSenha] = useState(false);
  const [showConfirmarSenha, setShowConfirmarSenha] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<SenhaForm>({
    resolver: zodResolver(senhaSchema),
  });

  const novaSenha = watch("nova_senha", "");

  useEffect(() => {
    if (!token) {
      setIsValidToken(false);
      return;
    }

    let isMounted = true;
    const verifyToken = async () => {
      try {
        await api.get(`/auth/password/reset/verify?token=${encodeURIComponent(token)}`);
        if (isMounted) setIsValidToken(true);
      } catch (error) {
        if (isMounted) setIsValidToken(false);
      }
    };

    verifyToken();
    return () => {
      isMounted = false;
    };
  }, [token]);


  const onSubmit = async (data: SenhaForm) => {
    if (!token) return;

    setIsLoading(true);
    try {
      await api.post("/auth/password/reset/confirm", {
        token,
        new_password: data.nova_senha,
        confirm_password: data.confirmar_senha,
      });
      setIsSuccess(true);
      toast.success("Senha redefinida com sucesso!");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  // Requisitos de senha
  const senhaRequisitos = [
    { regex: /.{8,}/, texto: "Mínimo 8 caracteres" },
    { regex: /[A-Z]/, texto: "Uma letra maiúscula" },
    { regex: /[a-z]/, texto: "Uma letra minúscula" },
    { regex: /[0-9]/, texto: "Um número" },
  ];

  // Token inválido ou expirado
  if (isValidToken === false) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center">
              <div className="p-4 bg-red-100 dark:bg-red-900/30 rounded-full mb-4">
                <XCircle className="w-12 h-12 text-red-600 dark:text-red-400" />
              </div>
              
              <h2 className="text-2xl font-bold">Link Inválido</h2>
              
              <p className="mt-2 text-muted-foreground">
                Este link de recuperação é inválido ou expirou. 
                Os links de recuperação são válidos por apenas 1 hora.
              </p>

              <div className="mt-6 flex flex-col gap-3 w-full">
                <Link href="/esqueci-senha" className="w-full">
                  <Button className="w-full">
                    Solicitar novo link
                  </Button>
                </Link>
                
                <Link href="/login" className="w-full">
                  <Button variant="ghost" className="w-full">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Voltar ao login
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Validando token
  if (isValidToken === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center">
              <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
              <p className="text-muted-foreground">Validando link de recuperação...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Sucesso
  if (isSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center">
              <div className="p-4 bg-green-100 dark:bg-green-900/30 rounded-full mb-4">
                <CheckCircle className="w-12 h-12 text-green-600 dark:text-green-400" />
              </div>
              
              <h2 className="text-2xl font-bold">Senha Redefinida!</h2>
              
              <p className="mt-2 text-muted-foreground">
                Sua senha foi alterada com sucesso. 
                Você já pode fazer login com sua nova senha.
              </p>

              <Link href="/login" className="w-full mt-6">
                <Button className="w-full">
                  Ir para o login
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex items-center gap-2">
              <Clock className="h-8 w-8 text-primary" />
              <span className="text-2xl font-bold">VibePonto</span>
            </div>
          </div>
          <CardTitle className="text-2xl">Redefinir senha</CardTitle>
          <CardDescription>
            Digite sua nova senha abaixo
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nova_senha">Nova Senha</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="nova_senha"
                  type={showNovaSenha ? "text" : "password"}
                  className="pl-9 pr-9"
                  {...register("nova_senha")}
                />
                <button
                  type="button"
                  onClick={() => setShowNovaSenha(!showNovaSenha)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showNovaSenha ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.nova_senha && (
                <p className="text-sm text-destructive">{errors.nova_senha.message}</p>
              )}
              
              {/* Requisitos de senha */}
              <div className="mt-2 p-3 bg-muted rounded-lg space-y-1">
                {senhaRequisitos.map((req, i) => (
                  <div 
                    key={i}
                    className={`flex items-center gap-2 text-xs ${
                      req.regex.test(novaSenha) 
                        ? "text-green-600 dark:text-green-400" 
                        : "text-muted-foreground"
                    }`}
                  >
                    {req.regex.test(novaSenha) ? (
                      <CheckCircle className="w-3 h-3" />
                    ) : (
                      <div className="w-3 h-3 rounded-full border" />
                    )}
                    {req.texto}
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmar_senha">Confirmar Nova Senha</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="confirmar_senha"
                  type={showConfirmarSenha ? "text" : "password"}
                  className="pl-9 pr-9"
                  {...register("confirmar_senha")}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmarSenha(!showConfirmarSenha)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showConfirmarSenha ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.confirmar_senha && (
                <p className="text-sm text-destructive">{errors.confirmar_senha.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Lock className="mr-2 h-4 w-4" />
              )}
              Redefinir senha
            </Button>

            <Link href="/login">
              <Button variant="ghost" className="w-full">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Voltar ao login
              </Button>
            </Link>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}


export default function RedefinirSenhaPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center">
              <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
              <p className="text-muted-foreground">Carregando...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    }>
      <RedefinirSenhaContent />
    </Suspense>
  );
}
