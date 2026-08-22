import { render, screen } from '@testing-library/react'
import Page from '../src/app/page'

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    replace: jest.fn(),
  }),
}))

jest.mock('@/lib/auth', () => ({
  useAuth: () => ({ user: null, loading: true }),
}))

describe('Home Page', () => {
  it('renders clinical copilot brand title', () => {
    render(<Page />)
    const text = screen.getByText('Clinical Copilot')
    expect(text).toBeDefined()
  })
})
