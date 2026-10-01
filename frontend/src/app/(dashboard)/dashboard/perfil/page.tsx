"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { getInitials } from "@/lib/utils";
import {
  User,
  Mail,
  Phone,
  Lock,
  Save,
  Loader2,
  Camera,
} from "lucide-react";
import { useState, useRef } from "react";

const perfilSchema = z.object({
  nome: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  email: z.string().email("Email inválido"),
  telefone: z.string().optional(),
});

const senhaSchema = z.object({
  senha_atual: z.string().min(1, "Senha atual é obrigatória"),
  nova_senha: z.string().min(8, "Senha deve ter pelo menos 8 caracteres"),
  confirmar_senha: z.string(),
}).refine((data) => data.nova_senha === data.confirmar_senha, {
  message: "Senhas não conferem",
  path: ["confirmar_senha"],
});

type PerfilForm = z.infer<typeof perfilSchema>;
type SenhaForm = z.infer<typeof senhaSchema>;

export default function PerfilPage() {
  const queryClient = useQueryClient();
  const { user, updateUser } = useAuthStore();
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: userData, isLoading } = useQuery({
    queryKey: ["meu-perfil"],
    queryFn: async () => {
      const response = await api.get("/auth/me");
      return response.data;
    },
  });

  const perfilForm = useForm<PerfilForm>({
    resolver: zodResolver(perfilSchema),
    values: userData ? {
      nome: userData.nome || "",
      email: userData.email || "",
      telefone: userData.telefone || "",
    } : undefined,
  });

  const senhaForm = useForm<SenhaForm>({
    resolver: zodResolver(senhaSchema),
  });

  const updatePerfilMutation = useMutation({
    mutationFn: async (data: PerfilForm) => {
      const response = await api.patch("/auth/me", {
        nome: data.nome,
        telefone: data.telefone,
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["meu-perfil"] });
      if (user) {
        updateUser({ nome: data.nome, email: data.email });
      }
      toast.success("Perfil atualizado com sucesso!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateSenhaMutation = useMutation({
    mutationFn: async (data: SenhaForm) => {
      await api.post("/auth/password/change", {
        current_password: data.senha_atual,
        new_password: data.nova_senha,
        confirm_password: data.confirmar_senha,
      });
    },
    onSuccess: () => {
      toast.success("Senha alterada com sucesso!");
      senhaForm.reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    toast.error('Upload de foto em breve.');
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Meu Perfil</h2>
        <p className="text-muted-foreground">
          Gerencie suas informações pessoais
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Avatar Card */}
        <Card>
          <CardHeader>
            <CardTitle>Foto de Perfil</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            {isLoading ? (
              <Skeleton className="h-32 w-32 rounded-full" />
            ) : (
              <div className="relative">
                <Avatar className="h-32 w-32">
                  <AvatarImage src={userData?.foto_url} />
                  <AvatarFallback className="text-3xl">{getInitials(userData?.nome || "")}</AvatarFallback>
                </Avatar>
                <Button
                  size="icon"
                  variant="outline"
                  className="absolute bottom-0 right-0 rounded-full cursor-not-allowed opacity-60"
                  onClick={() => toast.error("Upload de foto estará disponível em breve.")}
                  disabled={true}
                  title="Upload de foto estará disponível em breve"
                >
                  <Camera className="h-4 w-4" />
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoUpload}
                  className="hidden"
                  disabled={true}
                />
              </div>
            )}
            <div className="mt-4 text-center">
              <p className="font-medium">{userData?.nome}</p>
              <p className="text-sm text-muted-foreground">{userData?.email}</p>
              <p className="text-xs text-muted-foreground capitalize mt-1">{userData?.papel?.replace("_", " ")}</p>
            </div>
          </CardContent>
        </Card>

        {/* Dados Pessoais */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Dados Pessoais</CardTitle>
            <CardDescription>Atualize suas informações</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                {Array(3).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <form onSubmit={perfilForm.handleSubmit((data) => updatePerfilMutation.mutate(data))} className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <User className="h-4 w-4" />
                      Nome Completo
                    </Label>
                    <Input {...perfilForm.register("nome")} />
                    {perfilForm.formState.errors.nome && (
                      <p className="text-sm text-destructive">{perfilForm.formState.errors.nome.message}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label className="flex items-center gap-2">
                      <Mail className="h-4 w-4" />
                      Email (Somente leitura)
                    </Label>
                    <Input {...perfilForm.register("email")} type="email" disabled className="bg-muted cursor-not-allowed" />
                    {perfilForm.formState.errors.email && (
                      <p className="text-sm text-destructive">{perfilForm.formState.errors.email.message}</p>
                    )}
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label className="flex items-center gap-2">
                      <Phone className="h-4 w-4" />
                      Telefone
                    </Label>
                    <Input {...perfilForm.register("telefone")} placeholder="(00) 00000-0000" />
                  </div>
                </div>
                <div className="flex justify-end">
                  <Button type="submit" disabled={updatePerfilMutation.isPending}>
                    {updatePerfilMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Salvar
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Alterar Senha */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Alterar Senha
          </CardTitle>
          <CardDescription>Mantenha sua conta segura</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={senhaForm.handleSubmit((data) => updateSenhaMutation.mutate(data))} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Senha Atual</Label>
                <Input {...senhaForm.register("senha_atual")} type="password" />
                {senhaForm.formState.errors.senha_atual && (
                  <p className="text-sm text-destructive">{senhaForm.formState.errors.senha_atual.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label>Nova Senha</Label>
                <Input {...senhaForm.register("nova_senha")} type="password" />
                {senhaForm.formState.errors.nova_senha && (
                  <p className="text-sm text-destructive">{senhaForm.formState.errors.nova_senha.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label>Confirmar Nova Senha</Label>
                <Input {...senhaForm.register("confirmar_senha")} type="password" />
                {senhaForm.formState.errors.confirmar_senha && (
                  <p className="text-sm text-destructive">{senhaForm.formState.errors.confirmar_senha.message}</p>
                )}
              </div>
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={updateSenhaMutation.isPending}>
                {updateSenhaMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Lock className="mr-2 h-4 w-4" />}
                Alterar Senha
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
