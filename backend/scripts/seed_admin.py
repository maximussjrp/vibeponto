"""Script para criar usuário admin de teste."""
import asyncio
import bcrypt
import asyncpg


async def main():
    conn = await asyncpg.connect(
        'postgresql://vibeponto:vibeponto_dev_123@postgres:5432/vibeponto'
    )
    
    # Gerar hash
    password_hash = bcrypt.hashpw(b'Admin@123', bcrypt.gensalt()).decode()
    print(f'Hash gerado: {password_hash}')
    
    # Atualizar senha
    await conn.execute(
        'UPDATE vibeponto.usuarios SET password_hash = $1 WHERE email = $2',
        password_hash, 
        'admin@demo.com'
    )
    
    # Verificar
    row = await conn.fetchrow(
        'SELECT password_hash FROM vibeponto.usuarios WHERE email = $1', 
        'admin@demo.com'
    )
    print(f'Hash salvo: {row["password_hash"]}')
    
    await conn.close()
    print('Senha atualizada com sucesso!')


if __name__ == '__main__':
    asyncio.run(main())
