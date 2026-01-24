"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { authService } from "@/services/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Eye, EyeOff, Clock, Building2, User, CreditCard, ArrowLeft, ArrowRight, Check } from "lucide-react";

const registerSchema = z.object({
  // Empresa
  empresa_nome: z.string().min(3, "Nome da empresa deve ter pelo menos 3 caracteres"),
  empresa_cnpj: z.string().min(14, "CNPJ inválido").max(18, "CNPJ inválido"),
  empresa_email: z.string().email("Email inválido"),
  empresa_telefone: z.string().optional(),
  
  // Admin
  admin_nome: z.string().min(3, "Nome deve ter pelo menos 3 caracteres"),
  admin_email: z.string().email("Email inválido"),
  admin_senha: z.string().min(8, "Senha deve ter pelo menos 8 caracteres")
    .regex(/[A-Z]/, "Senha deve conter pelo menos uma letra maiúscula")
    .regex(/[a-z]/, "Senha deve conter pelo menos uma letra minúscula")
    .regex(/[0-9]/, "Senha deve conter pelo menos um número"),
  admin_senha_confirmacao: z.string(),
  
  // Plano
  plano: z.enum(["starter", "professional", "enterprise"]),
  
  // Termos
  aceito_termos: z.boolean().refine(val => val === true, "Você deve aceitar os termos"),
}).refine((data) => data.admin_senha === data.admin_senha_confirmacao, {
  message: "As senhas não coincidem",
  path: ["admin_senha_confirmacao"],
});

type RegisterForm = z.infer<typeof registerSchema>;

const planos = [
  {
    id: "starter" as const,
    nome: "Starter",
    preco: "R$ 4,90",
    periodo: "/colaborador/mês",
    recursos: [
      "Até 50 colaboradores",
      "Registro de ponto básico",
      "Relatórios essenciais",
      "Suporte por email",
    ],
    destaque: false,
  },
  {
    id: "professional" as const,
    nome: "Professional",
    preco: "R$ 9,90",
    periodo: "/colaborador/mês",
    recursos: [
      "Até 200 colaboradores",
      "Geolocalização e foto",
      "Perímetros ilimitados",
      "Relatórios avançados",
      "App mobile",
      "Suporte prioritário",
    ],
    destaque: true,
  },
  {
    id: "enterprise" as const,
    nome: "Enterprise",
    preco: "Sob consulta",
    periodo: "",
    recursos: [
      "Colaboradores ilimitados",
      "API completa",
      "SSO / SAML",
      "Integrações customizadas",
      "SLA garantido",
      "Gerente de conta dedicado",
    ],
    destaque: false,
  },
];

const steps = [
  { id: 1, nome: "Empresa", icon: Building2 },
  { id: 2, nome: "Administrador", icon: User },
  { id: 3, nome: "Plano", icon: CreditCard },
];

export default function RegisterPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    setValue,
    trigger,
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      plano: "professional",
      aceito_termos: false,
    },
  });

  const selectedPlano = watch("plano");

  const formatCNPJ = (value: string) => {
    const numbers = value.replace(/\D/g, "");
    return numbers
      .replace(/(\d{2})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1/$2")
      .replace(/(\d{4})(\d)/, "$1-$2")
      .slice(0, 18);
  };

  const formatPhone = (value: string) => {
    const numbers = value.replace(/\D/g, "");
    if (numbers.length <= 10) {
      return numbers
        .replace(/(\d{2})(\d)/, "($1) $2")
        .replace(/(\d{4})(\d)/, "$1-$2");
    }
    return numbers
      .replace(/(\d{2})(\d)/, "($1) $2")
      .replace(/(\d{5})(\d)/, "$1-$2")
      .slice(0, 15);
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof RegisterForm)[] = [];
    
    if (currentStep === 1) {
      fieldsToValidate = ["empresa_nome", "empresa_cnpj", "empresa_email"];
    } else if (currentStep === 2) {
      fieldsToValidate = ["admin_nome", "admin_email", "admin_senha", "admin_senha_confirmacao"];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid) {
      setCurrentStep((prev) => Math.min(prev + 1, 3));
    }
  };

  const prevStep = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true);

    try {
      await authService.registerTenant({
        empresa_nome: data.empresa_nome,
        empresa_cnpj: data.empresa_cnpj.replace(/\D/g, ""),
        empresa_email: data.empresa_email,
        empresa_telefone: data.empresa_telefone?.replace(/\D/g, ""),
        admin_nome: data.admin_nome,
        admin_email: data.admin_email,
        admin_senha: data.admin_senha,
        plano: data.plano,
      });

      toast.success("Cadastro realizado com sucesso! Verifique seu email.");
      router.push("/login?registered=true");
    } catch (error) {
      toast.error(getErrorMessage(error));
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/20 via-background to-primary/10 p-4">
      <div className="w-full max-w-2xl">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary text-primary-foreground">
            <Clock className="w-7 h-7" />
          </div>
          <span className="text-2xl font-bold">VibePonto</span>
        </div>

        {/* Steps */}
        <div className="flex items-center justify-center mb-8">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors ${
                  currentStep >= step.id
                    ? "bg-primary border-primary text-primary-foreground"
                    : "border-muted-foreground/30 text-muted-foreground"
                }`}
              >
                {currentStep > step.id ? (
                  <Check className="w-5 h-5" />
                ) : (
                  <step.icon className="w-5 h-5" />
                )}
              </div>
              <span
                className={`ml-2 text-sm font-medium ${
                  currentStep >= step.id ? "text-foreground" : "text-muted-foreground"
                }`}
              >
                {step.nome}
              </span>
              {index < steps.length - 1 && (
                <div
                  className={`w-12 h-0.5 mx-4 ${
                    currentStep > step.id ? "bg-primary" : "bg-muted-foreground/30"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">
              {currentStep === 1 && "Dados da Empresa"}
              {currentStep === 2 && "Administrador da Conta"}
              {currentStep === 3 && "Escolha seu Plano"}
            </CardTitle>
            <CardDescription>
              {currentStep === 1 && "Informe os dados da sua empresa para criar sua conta"}
              {currentStep === 2 && "Configure o usuário administrador principal"}
              {currentStep === 3 && "Selecione o plano ideal para sua empresa"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)}>
              {/* Step 1: Empresa */}
              {currentStep === 1 && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="empresa_nome">Nome da Empresa *</Label>
                    <Input
                      id="empresa_nome"
                      placeholder="Minha Empresa LTDA"
                      {...register("empresa_nome")}
                    />
                    {errors.empresa_nome && (
                      <p className="text-sm text-destructive">{errors.empresa_nome.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="empresa_cnpj">CNPJ *</Label>
                    <Input
                      id="empresa_cnpj"
                      placeholder="00.000.000/0000-00"
                      {...register("empresa_cnpj", {
                        onChange: (e) => {
                          e.target.value = formatCNPJ(e.target.value);
                        },
                      })}
                    />
                    {errors.empresa_cnpj && (
                      <p className="text-sm text-destructive">{errors.empresa_cnpj.message}</p>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="empresa_email">Email Corporativo *</Label>
                      <Input
                        id="empresa_email"
                        type="email"
                        placeholder="contato@empresa.com"
                        {...register("empresa_email")}
                      />
                      {errors.empresa_email && (
                        <p className="text-sm text-destructive">{errors.empresa_email.message}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="empresa_telefone">Telefone</Label>
                      <Input
                        id="empresa_telefone"
                        placeholder="(00) 00000-0000"
                        {...register("empresa_telefone", {
                          onChange: (e) => {
                            e.target.value = formatPhone(e.target.value);
                          },
                        })}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Admin */}
              {currentStep === 2 && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="admin_nome">Nome Completo *</Label>
                    <Input
                      id="admin_nome"
                      placeholder="João da Silva"
                      {...register("admin_nome")}
                    />
                    {errors.admin_nome && (
                      <p className="text-sm text-destructive">{errors.admin_nome.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="admin_email">Email do Administrador *</Label>
                    <Input
                      id="admin_email"
                      type="email"
                      placeholder="admin@empresa.com"
                      {...register("admin_email")}
                    />
                    {errors.admin_email && (
                      <p className="text-sm text-destructive">{errors.admin_email.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="admin_senha">Senha *</Label>
                    <div className="relative">
                      <Input
                        id="admin_senha"
                        type={showPassword ? "text" : "password"}
                        placeholder="••••••••"
                        {...register("admin_senha")}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    {errors.admin_senha && (
                      <p className="text-sm text-destructive">{errors.admin_senha.message}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Mínimo 8 caracteres, com maiúscula, minúscula e número
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="admin_senha_confirmacao">Confirmar Senha *</Label>
                    <div className="relative">
                      <Input
                        id="admin_senha_confirmacao"
                        type={showConfirmPassword ? "text" : "password"}
                        placeholder="••••••••"
                        {...register("admin_senha_confirmacao")}
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    {errors.admin_senha_confirmacao && (
                      <p className="text-sm text-destructive">{errors.admin_senha_confirmacao.message}</p>
                    )}
                  </div>
                </div>
              )}

              {/* Step 3: Plano */}
              {currentStep === 3 && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {planos.map((plano) => (
                      <div
                        key={plano.id}
                        onClick={() => setValue("plano", plano.id)}
                        className={`relative cursor-pointer rounded-lg border-2 p-4 transition-all hover:border-primary/50 ${
                          selectedPlano === plano.id
                            ? "border-primary bg-primary/5"
                            : "border-border"
                        } ${plano.destaque ? "ring-2 ring-primary ring-offset-2" : ""}`}
                      >
                        {plano.destaque && (
                          <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-primary text-primary-foreground text-xs font-medium rounded-full">
                            Mais Popular
                          </div>
                        )}
                        <div className="text-center mb-4">
                          <h3 className="font-semibold text-lg">{plano.nome}</h3>
                          <div className="mt-2">
                            <span className="text-2xl font-bold">{plano.preco}</span>
                            <span className="text-sm text-muted-foreground">{plano.periodo}</span>
                          </div>
                        </div>
                        <ul className="space-y-2">
                          {plano.recursos.map((recurso, index) => (
                            <li key={index} className="flex items-center gap-2 text-sm">
                              <Check className="w-4 h-4 text-primary" />
                              {recurso}
                            </li>
                          ))}
                        </ul>
                        <input
                          type="radio"
                          {...register("plano")}
                          value={plano.id}
                          className="sr-only"
                        />
                      </div>
                    ))}
                  </div>

                  <div className="flex items-start gap-2 p-4 bg-muted/50 rounded-lg">
                    <input
                      type="checkbox"
                      id="aceito_termos"
                      {...register("aceito_termos")}
                      className="mt-1"
                    />
                    <label htmlFor="aceito_termos" className="text-sm">
                      Li e aceito os{" "}
                      <a href="/termos" className="text-primary hover:underline">
                        Termos de Uso
                      </a>{" "}
                      e a{" "}
                      <a href="/privacidade" className="text-primary hover:underline">
                        Política de Privacidade
                      </a>
                    </label>
                  </div>
                  {errors.aceito_termos && (
                    <p className="text-sm text-destructive">{errors.aceito_termos.message}</p>
                  )}
                </div>
              )}

              {/* Navigation */}
              <div className="flex justify-between mt-8">
                {currentStep > 1 ? (
                  <Button type="button" variant="outline" onClick={prevStep}>
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Voltar
                  </Button>
                ) : (
                  <Link href="/login">
                    <Button type="button" variant="ghost">
                      <ArrowLeft className="w-4 h-4 mr-2" />
                      Já tenho conta
                    </Button>
                  </Link>
                )}

                {currentStep < 3 ? (
                  <Button type="button" onClick={nextStep}>
                    Próximo
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                ) : (
                  <Button type="submit" disabled={isLoading}>
                    {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Criar Conta
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-muted-foreground mt-6">
          © 2026 VibePonto. Todos os direitos reservados.
        </p>
      </div>
    </div>
  );
}
