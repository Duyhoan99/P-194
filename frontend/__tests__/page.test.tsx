import '@testing-library/jest-dom'
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
  it('renders loading text', () => {
    render(<Page />)
    const text = screen.getByText('Đang tải...')
    expect(text).toBeInTheDocument()
  })
})
